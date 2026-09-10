"""重复记录对比服务：新抓取 vs 数据库已有记录"""
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

import database
from services.url_normalizer import normalize_url
from services.source_detector import detect_both
from services.url_fetcher import fetch_url, FetchResult

# 人工字段：不覆盖
_PROTECTED = {
    "summary", "business_value", "querit_status", "gap_analysis",
    "suggested_action", "priority", "review_status", "follow_up_status",
    "manual_note",
}

_STATUS_LABEL = {
    "success":    "抓取成功",
    "partial":    "部分获取",
    "restricted": "访问受限",
    "failed":     "抓取失败",
    "duplicate":  "已存在",
    "pending":    "待抓取",
}


@dataclass
class RefetchComparison:
    """旧记录 vs 本次抓取结果。"""
    original_url: str
    normalized_url: str
    # 数据库已有记录
    existing_id: int = 0
    existing_competitor: str = ""
    existing_platform: str = ""
    existing_fetch_status: str = ""
    existing_fetch_error: str = ""
    existing_http_status: str = ""
    existing_review_status: str = ""
    existing_updated_at: str = ""
    # 本次抓取结果
    new_competitor: str = ""
    new_platform: str = ""
    new_fetch_status: str = ""
    new_fetch_error: str = ""
    new_http_status: str = ""
    new_title: str = ""
    new_published_date: str = ""
    new_needs_manual: bool = False
    fetched_at: str = ""
    # 状态变化说明
    status_changed: bool = False
    status_transition_msg: str = ""


def fetch_and_compare(url: str) -> Optional[RefetchComparison]:
    """对已存在的 URL 执行新抓取，返回对比结果。若 URL 不在 DB 中返回 None。"""
    norm = normalize_url(url)
    existing = database.get_record_by_url(norm)
    if not existing:
        return None

    comp = RefetchComparison(
        original_url=url,
        normalized_url=norm,
        existing_id=existing.get("id", 0),
        existing_competitor=existing.get("competitor") or "",
        existing_platform=existing.get("source_platform") or "",
        existing_fetch_status=existing.get("fetch_status") or "",
        existing_fetch_error=existing.get("fetch_error") or "",
        existing_http_status=str(existing.get("http_status_code") or ""),
        existing_review_status=existing.get("review_status") or "",
        existing_updated_at=(existing.get("updated_at") or "")[:19],
    )

    now = datetime.now(timezone.utc).isoformat()[:19].replace("T", " ")
    comp.fetched_at = now

    # 本次抓取
    detected = detect_both(url)
    fr = fetch_url(url)

    comp.new_competitor = detected["competitor"]
    comp.new_platform = detected["source_platform"]
    comp.new_fetch_status = fr.status
    comp.new_fetch_error = fr.error or ""
    comp.new_http_status = str(fr.http_status_code) if fr.http_status_code else ""
    comp.new_title = fr.title or ""
    comp.new_published_date = fr.published_date or ""
    comp.new_needs_manual = fr.status in ("restricted", "failed", "partial")

    # 状态变化说明
    old_s = comp.existing_fetch_status
    new_s = comp.new_fetch_status
    old_label = _STATUS_LABEL.get(old_s, old_s)
    new_label = _STATUS_LABEL.get(new_s, new_s)

    if old_s != new_s:
        comp.status_changed = True
        comp.status_transition_msg = f"本次抓取结果已更新：{old_label} → {new_label}"
    else:
        comp.status_transition_msg = f"状态无变化（{old_label}）"

    return comp


def apply_refetch_result(comp: RefetchComparison) -> dict:
    """将本次抓取结果写入数据库，不覆盖人工字段。返回更新结果摘要。"""
    if not comp.existing_id:
        return {"ok": False, "message": "无效记录 ID"}

    # 读取当前记录（避免竞争）
    with database._get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM competitor_updates WHERE id = ?", (comp.existing_id,)
        ).fetchone()
    if not row:
        return {"ok": False, "message": f"记录 ID={comp.existing_id} 不存在"}

    existing_rec = dict(row)
    updates: dict = {}

    # fetch 字段直接覆盖（来自 comp，不再重复发起网络请求）
    updates["fetch_status"] = comp.new_fetch_status
    updates["fetch_error"] = comp.new_fetch_error or None
    updates["final_url"] = comp.original_url  # restricted 时无 final_url

    if comp.new_title:
        updates["raw_title"] = comp.new_title

    # 仅在原来为空时更新 title
    old_title = existing_rec.get("title") or ""
    if comp.new_title and (not old_title or old_title == comp.original_url):
        updates["title"] = comp.new_title

    # 仅在原来为空时更新 publish_date
    if comp.new_published_date and not existing_rec.get("publish_date"):
        updates["publish_date"] = comp.new_published_date

    # competitor / source_platform 若原来是 Other 则更新
    if comp.new_competitor and (
        not existing_rec.get("competitor") or existing_rec["competitor"] == "Other"
    ):
        updates["competitor"] = comp.new_competitor
    if comp.new_platform and (
        not existing_rec.get("source_platform") or existing_rec["source_platform"] == "Other"
    ):
        updates["source_platform"] = comp.new_platform

    ok = database.update_record(comp.existing_id, updates)
    return {
        "ok": ok,
        "record_id": comp.existing_id,
        "old_status": comp.existing_fetch_status,
        "new_status": comp.new_fetch_status,
        "transition_msg": comp.status_transition_msg,
        "updated_at": datetime.now(timezone.utc).isoformat()[:19].replace("T", " "),
    }
