"""业务数据服务：周次计算、批量插入、审核操作、历史查询、导出"""
import io
from datetime import date, datetime, timezone

import pandas as pd

import database
from config import (
    CATEGORIES,
    COMPETITORS,
    PRIORITY_OPTIONS,
    QUERIT_STATUS_OPTIONS,
    SOURCE_PLATFORMS,
)


# ── 周次 ──────────────────────────────────────────────────────

def get_current_week_id() -> str:
    """返回当前 ISO 周次字符串，如 '2026-W30'。"""
    today = date.today()
    iso = today.isocalendar()
    return f"{iso.year}-W{iso.week:02d}"


# ── 看板查询 ──────────────────────────────────────────────────

def get_weekly_dashboard(week_id: str | None = None, extra_filters: dict | None = None) -> list[dict]:
    """返回指定周（默认当前周）、review_status=已确认 的记录。"""
    filters: dict = {"week_id": week_id or get_current_week_id(), "review_status": "已确认"}
    if extra_filters:
        filters.update(extra_filters)
    return database.get_records(filters)


# ── 批量插入 ──────────────────────────────────────────────────

def batch_insert(records: list[dict]) -> dict:
    """批量插入，返回 {"success": N, "duplicate": N, "error": N, "errors": [...]}。"""
    result = {"success": 0, "duplicate": 0, "error": 0, "errors": []}
    for rec in records:
        status = database.insert_record(rec)
        if status == "success":
            result["success"] += 1
        elif status == "duplicate":
            result["duplicate"] += 1
        else:
            result["error"] += 1
            result["errors"].append(status)
    return result


# ── 审核区 ────────────────────────────────────────────────────

def get_pending_review() -> list[dict]:
    """返回所有 review_status=待审核 的记录。"""
    return database.get_records({"review_status": "待审核"})


def confirm_record(record_id: int, updates: dict | None = None) -> bool:
    """标记记录为已确认，同时保存编辑字段。"""
    fields = dict(updates or {})
    fields["review_status"] = "已确认"
    return database.update_record(record_id, fields)


def ignore_record(record_id: int) -> bool:
    """标记记录为已忽略。"""
    return database.update_record(record_id, {"review_status": "已忽略"})


# ── 重新抓取并更新 ─────────────────────────────────────────────

# 禁止覆盖的人工字段
_PROTECTED_FIELDS = {
    "summary", "business_value", "querit_status", "gap_analysis",
    "suggested_action", "priority", "review_status", "follow_up_status",
}


def refetch_and_update(record_id: int, url: str) -> dict:
    """重新抓取指定 URL，仅更新抓取类字段，不覆盖人工字段。
    抓取成功/部分成功后，对空白分析字段补充自动预分析。
    
    Returns: {"status": "success"|"partial"|"failed"|"restricted", "message": str}
    """
    from services.url_fetcher import fetch_url as _fetch_url
    from services.source_detector import detect_both
    from services.github_analyzer import analyze_github_content
    from services.content_analyzer import analyze_record

    existing = database.get_records()
    # 查找记录
    with database._get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM competitor_updates WHERE id = ?", (record_id,)
        ).fetchone()
    if not row:
        return {"status": "failed", "message": f"记录 ID={record_id} 不存在"}

    existing_rec = dict(row)

    # 执行抓取
    fr = _fetch_url(url)

    # 构建更新字段（只更新抓取相关，不覆盖人工字段）
    updates: dict = {
        "fetch_status": fr.status,
        "fetch_error": fr.error or None,
        "final_url": fr.final_url or url,
        "raw_title": fr.title or None,
        "raw_content": fr.content_snippet[:2000] if fr.content_snippet else None,
        "content_source": fr.content_source or None,
    }

    # title：仅在原来为空或等于 URL 本身时才更新
    old_title = existing_rec.get("title") or ""
    if fr.title and (not old_title or old_title == url):
        updates["title"] = fr.title

    # publish_date：仅原字段为空时更新
    if fr.published_date and not existing_rec.get("publish_date"):
        updates["publish_date"] = fr.published_date

    # competitor / source_platform：若原来是 Other 则更新
    detected = detect_both(url)
    if (not existing_rec.get("competitor") or existing_rec["competitor"] == "Other"):
        updates["competitor"] = detected["competitor"]
    if (not existing_rec.get("source_platform") or existing_rec["source_platform"] == "Other"):
        updates["source_platform"] = detected["source_platform"]

    # GitHub 分析（若来源是 GitHub）
    if detected["source_platform"] == "GitHub" or existing_rec.get("source_platform") == "GitHub":
        try:
            gh = analyze_github_content(url, fr.title, fr.description, fr.content_snippet)
            for k, v in gh.items():
                if k not in _PROTECTED_FIELDS:
                    updates[k] = v
        except Exception:
            pass

    # 执行数据库更新
    ok = database.update_record(record_id, updates)

    # 抓取成功/部分成功后，对空白分析字段补充自动预分析
    if ok and fr.status in ("success", "partial"):
        merged_rec = {**existing_rec, **updates}
        try:
            analysis = analyze_record(merged_rec)
            fill_fields = analysis.to_fill_fields(merged_rec)
            # 只传递分析字段，不重复写抓取字段
            analysis_only = {k: v for k, v in fill_fields.items()
                             if k not in updates}
            if analysis_only:
                database.update_record(record_id, analysis_only)
        except Exception:
            pass

    if ok:
        msg = f"更新成功（fetch_status={fr.status}）"
    else:
        msg = "数据库更新失败"

    return {"status": fr.status, "message": msg, "updates_applied": list(updates.keys())}


# ── 历史查询 ──────────────────────────────────────────────────

def get_history(filters: dict | None = None) -> list[dict]:
    """返回所有已确认的历史数据，支持多条件筛选。"""
    f = dict(filters or {})
    f["review_status"] = "已确认"
    return database.get_records(f)


# ── 导出 Excel ────────────────────────────────────────────────

_EXPORT_COLUMNS = [
    ("publish_date", "发布时间"),
    ("competitor", "竞品"),
    ("category", "分类"),
    ("title", "动态标题"),
    ("summary", "动态概述"),
    ("source_url", "原始链接"),
    ("source_platform", "信息平台"),
    ("querit_status", "Querit状态"),
    ("priority", "优先级"),
    ("gap_analysis", "差距判断"),
    ("suggested_action", "建议动作"),
    ("week_id", "周次"),
    ("review_status", "审核状态"),
]


def export_to_excel(records: list[dict]) -> bytes:
    """将记录列表导出为 Excel 字节流。"""
    if not records:
        df = pd.DataFrame(columns=[col for _, col in _EXPORT_COLUMNS])
    else:
        df = pd.DataFrame(records)
        rename_map = {db: display for db, display in _EXPORT_COLUMNS if db in df.columns}
        df = df[[col for col, _ in _EXPORT_COLUMNS if col in df.columns]]
        df = df.rename(columns=rename_map)

    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="竞品动态")
    return buf.getvalue()
