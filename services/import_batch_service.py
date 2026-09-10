"""批次服务：URL 列表处理、抓取、统一写入待审核区"""
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

import database
from services.url_normalizer import normalize_url, is_valid_url, deduplicate_urls
from services.source_detector import detect_both
from services.url_fetcher import fetch_url, FetchResult
from services.github_analyzer import analyze_github_content
from services.data_service import get_current_week_id


@dataclass
class BatchRecord:
    original_url: str
    normalized_url: str = ""
    competitor: str = "Other"
    source_platform: str = "Other"
    title: str = ""
    description: str = ""
    published_date: str = ""
    content_snippet: str = ""
    fetch_status: str = "pending"
    fetch_error: str = ""
    content_source: str = ""
    final_url: str = ""
    manual_note: str = ""
    is_duplicate: bool = False
    is_invalid_url: bool = False
    # 重复记录的已有信息
    duplicate_record_id: int = 0
    duplicate_competitor: str = ""
    duplicate_platform: str = ""
    duplicate_title: str = ""
    duplicate_fetch_status: str = ""
    duplicate_review_status: str = ""
    duplicate_updated_at: str = ""
    # GitHub 专项
    github_event_type: str = ""
    repository_name: str = ""
    docs_changed: int = 0
    capability_change: int = 0
    integration_change: int = 0
    developer_experience_change: int = 0
    change_summary: str = ""


def process_url_list(
    urls: list[str],
    manual_notes: Optional[list[str]] = None,
    progress_callback=None,
) -> list[BatchRecord]:
    """处理 URL 列表：normalize → DB去重 → detect → fetch → GitHub分析。
    
    progress_callback(current, total) 可选，用于进度反馈。
    单条失败不中断后续处理。
    """
    manual_notes = manual_notes or [""] * len(urls)
    # 同批次去重
    deduped = deduplicate_urls(urls)
    total = len(deduped)
    results: list[BatchRecord] = []

    # 记录去重的原始 URL
    seen_originals = set()

    for i, url in enumerate(deduped):
        if progress_callback:
            progress_callback(i, total)

        rec = BatchRecord(original_url=url)
        note_idx = urls.index(url) if url in urls else i
        rec.manual_note = manual_notes[note_idx] if note_idx < len(manual_notes) else ""

        # URL 格式校验
        if not is_valid_url(url):
            rec.is_invalid_url = True
            rec.fetch_status = "failed"
            rec.fetch_error = "URL 格式无效"
            results.append(rec)
            continue

        rec.normalized_url = normalize_url(url)

        # DB 去重
        if database.is_url_duplicate(rec.normalized_url):
            rec.is_duplicate = True
            rec.fetch_status = "duplicate"
            # 查询数据库中已有记录，填充重复字段信息
            existing = database.get_record_by_url(rec.normalized_url)
            if existing:
                rec.duplicate_record_id = existing.get("id", 0)
                rec.duplicate_competitor = existing.get("competitor") or ""
                rec.duplicate_platform = existing.get("source_platform") or ""
                rec.duplicate_title = existing.get("title") or ""
                rec.duplicate_fetch_status = existing.get("fetch_status") or ""
                rec.duplicate_review_status = existing.get("review_status") or ""
                rec.duplicate_updated_at = (existing.get("updated_at") or "")[:19]
            # 使用来源识别补全空竞品/平台（仅用于预览展示）
            detected = detect_both(url)
            # 已有竞品为 Other 时，用识别结果替换预览字段
            rec.competitor = (rec.duplicate_competitor if rec.duplicate_competitor and rec.duplicate_competitor != "Other"
                              else detected["competitor"])
            rec.source_platform = rec.duplicate_platform or detected["source_platform"]
            results.append(rec)
            continue

        # 来源识别
        detected = detect_both(url)
        rec.competitor = detected["competitor"]
        rec.source_platform = detected["source_platform"]

        # 抓取
        try:
            fetch_result: FetchResult = fetch_url(url)
            rec.title = fetch_result.title
            rec.description = fetch_result.description
            rec.published_date = fetch_result.published_date
            rec.content_snippet = fetch_result.content_snippet
            rec.fetch_status = fetch_result.status
            rec.fetch_error = fetch_result.error
            rec.content_source = fetch_result.content_source
            rec.final_url = fetch_result.final_url or url
        except Exception as e:
            rec.fetch_status = "failed"
            rec.fetch_error = f"抓取异常：{str(e)[:100]}"

        # GitHub 专项分析
        if rec.source_platform == "GitHub":
            try:
                gh = analyze_github_content(
                    url,
                    title=rec.title,
                    description=rec.description,
                    content=rec.content_snippet,
                )
                rec.github_event_type = gh.get("github_event_type", "")
                rec.repository_name = gh.get("repository_name", "")
                rec.docs_changed = gh.get("docs_changed", 0)
                rec.capability_change = gh.get("capability_change", 0)
                rec.integration_change = gh.get("integration_change", 0)
                rec.developer_experience_change = gh.get("developer_experience_change", 0)
                rec.change_summary = gh.get("change_summary", "")
            except Exception:
                pass

        results.append(rec)

    if progress_callback:
        progress_callback(total, total)

    return results


def confirm_batch(
    records: list[BatchRecord],
    selected_indices: Optional[list[int]],
    import_mode: str = "url_batch",
) -> dict:
    """将选中记录写入 competitor_updates + import_batches。
    
    Returns: {"success": N, "duplicate": N, "failed": N, "restricted": N,
              "partial": N, "final_imported": N, "batch_id": str}
    """
    batch_id = str(uuid.uuid4())[:8]
    now = datetime.now(timezone.utc).isoformat()
    week_id = get_current_week_id()

    if selected_indices is None:
        selected_indices = list(range(len(records)))

    stats = {"success": 0, "duplicate": 0, "failed": 0,
             "restricted": 0, "partial": 0, "final_imported": 0}

    for idx in selected_indices:
        if idx >= len(records):
            continue
        rec = records[idx]

        # 跳过无效 URL（但不跳过 failed/restricted，让其进入待审核区）
        if rec.is_invalid_url:
            stats["failed"] += 1
            continue

        if rec.is_duplicate:
            stats["duplicate"] += 1
            continue

        # 统计抓取状态
        s = rec.fetch_status
        if s in stats:
            stats[s] += 1

        # 自动预分析
        from services.content_analyzer import analyze_record
        pre_rec_for_analysis = {
            "competitor": rec.competitor,
            "source_platform": rec.source_platform,
            "title": rec.title or "",
            "summary": rec.description or "",
            "raw_content": rec.content_snippet or "",
            "manual_note": rec.manual_note or "",
            "source_url": rec.original_url,
            "docs_changed": rec.docs_changed,
            "capability_change": rec.capability_change,
            "integration_change": rec.integration_change,
            "developer_experience_change": rec.developer_experience_change,
            "change_summary": rec.change_summary or "",
        }
        try:
            analysis = analyze_record(pre_rec_for_analysis)
        except Exception:
            analysis = None

        # 构建数据库记录
        db_rec = {
            "source_url": rec.original_url,
            "normalized_url": rec.normalized_url or normalize_url(rec.original_url),
            "final_url": rec.final_url,
            "competitor": rec.competitor,
            "source_platform": rec.source_platform,
            "title": rec.title or rec.original_url,
            "summary": rec.description,
            "publish_date": rec.published_date or None,
            "raw_title": rec.title,
            "raw_content": rec.content_snippet[:2000] if rec.content_snippet else None,
            "content_source": rec.content_source,
            "fetch_status": rec.fetch_status if rec.fetch_status not in ("duplicate", "pending") else "pending",
            "fetch_error": rec.fetch_error or None,
            "manual_note": rec.manual_note or None,
            "imported_batch_id": batch_id,
            "collected_at": now,
            "week_id": week_id,
            "review_status": "待审核",
            "source_mode": "url_batch" if import_mode != "manual_form" else "manual_form",
            # 初始分析字段（自动建议值）
            "category": analysis.auto_category if analysis else "待评估",
            "querit_status": "待评估",
            "priority": analysis.auto_priority if analysis else "中",
            "suggested_action": analysis.auto_suggested_action if analysis else None,
            "business_value": analysis.auto_business_value if analysis else None,
            "gap_analysis": analysis.auto_gap_analysis if analysis else None,
            "follow_up_status": "待处理",
            "updated_at": now,
            # GitHub
            "github_event_type": rec.github_event_type or None,
            "repository_name": rec.repository_name or None,
            "docs_changed": rec.docs_changed,
            "capability_change": rec.capability_change,
            "integration_change": rec.integration_change,
            "developer_experience_change": rec.developer_experience_change,
            "change_summary": rec.change_summary or None,
        }
        # 合并自动分析的 DB 字段
        if analysis:
            db_rec.update(analysis.to_db_fields())

        result = database.insert_record(db_rec)
        if result == "success":
            stats["final_imported"] += 1
        elif result == "duplicate":
            stats["duplicate"] += 1
            stats["final_imported"] = max(0, stats["final_imported"])

    # 写入批次记录
    database.insert_batch_record({
        "batch_id": batch_id,
        "created_at": now,
        "import_mode": import_mode,
        "total": len(records),
        "success": stats["success"],
        "partial": stats["partial"],
        "failed": stats["failed"],
        "restricted": stats["restricted"],
        "duplicate": stats["duplicate"],
        "final_imported": stats["final_imported"],
    })

    stats["batch_id"] = batch_id
    return stats
