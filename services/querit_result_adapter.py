"""Querit 检索结果适配器
将 Querit 原始结果 (SearchResult) 转换为系统现有记录结构。
竞品/平台识别优先级：URL 域名 > metadata > Query 竞品 > 标题摘要
不得仅因 Query 属于某竞品就强制覆盖 URL 识别结果。
"""
import json
from datetime import datetime, timezone
from typing import Optional

from services.querit_client import SearchResult
from services.url_normalizer import normalize_url, is_valid_url
from services.source_detector import detect_both
from services.page_type_classifier import classify_page_type, is_entry_page, is_import_eligible
from services.data_service import get_current_week_id
import database


def adapt_result(
    result: SearchResult,
    run_id: str,
    query_id: Optional[int],
    query_competitor: str = "Other",
    batch_id: str = "",
) -> Optional[dict]:
    """将单条 SearchResult 转换为 competitor_updates 兼容的字典。
    返回 None 表示该结果无效（缺 URL）。
    """
    url = result.url.strip()
    if not url or not is_valid_url(url):
        return None

    norm = normalize_url(url)
    now = datetime.now(timezone.utc).isoformat()

    # 竞品/平台识别（优先 URL 域名，无法识别时才用 Query 竞品）
    detected = detect_both(url, result.title, result.summary)
    competitor = detected["competitor"]
    if competitor == "Other" and query_competitor and query_competitor != "Other":
        competitor = query_competitor
    source_platform = detected["source_platform"]

    # 去重检查
    is_dup = database.is_url_duplicate(norm)
    existing_id = 0
    if is_dup:
        existing = database.get_record_by_url(norm)
        if existing:
            existing_id = existing.get("id", 0)

    # 页面类型识别
    pt = classify_page_type(url, result.title or "", source_platform)
    entry = is_entry_page(pt)
    eligible = is_import_eligible(pt)

    return {
        # 核心字段
        "source_url": url,
        "normalized_url": norm,
        "title": result.title or url,
        "summary": result.summary or "",
        "published_date": result.published_date or None,
        "publish_date": result.published_date or None,
        "raw_title": result.title or None,
        "raw_content": result.content[:2000] if result.content else None,
        "competitor": competitor,
        "source_platform": source_platform,
        "source_mode": "querit_api",
        "collected_at": now,
        "week_id": get_current_week_id(),
        "review_status": "待审核",
        "category": "待评估",
        "querit_status": "待评估",
        "priority": "中",
        "follow_up_status": "待处理",
        "imported_batch_id": batch_id or run_id,
        "updated_at": now,
        # Querit 专项字段
        "querit_query": result.query,
        "querit_rank": result.rank,
        "querit_score": result.score,
        "querit_raw_summary": result.summary,
        "querit_raw_metadata": json.dumps(result.raw_metadata, ensure_ascii=False)
                               if result.raw_metadata else None,
        # 页面类型字段
        "page_type": pt,
        "is_entry_page": 1 if entry else 0,
        "import_eligible": 1 if eligible else 0,
        "needs_drilldown": 1 if entry else 0,
        # 去重信息（仅用于预览层）
        "_is_duplicate": is_dup,
        "_existing_record_id": existing_id,
        "_run_id": run_id,
        "_query_id": query_id,
        # 入口页默认不选
        "_should_select_override": (not entry),  # 入口页强制不选
    }


def adapt_results(
    results: list[SearchResult],
    run_id: str,
    query_id: Optional[int],
    query_competitor: str = "Other",
    batch_id: str = "",
) -> list[dict]:
    """批量适配，跳过无效结果，单条异常不中断。"""
    adapted = []
    for r in results:
        try:
            rec = adapt_result(r, run_id, query_id, query_competitor, batch_id)
            if rec:
                adapted.append(rec)
        except Exception:
            pass
    return adapted
