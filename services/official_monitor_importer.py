"""官方巡检结果转换器 + 主结果过滤器（V3）
修复：
1. docs_pending 规则加入 effective_date 时间窗口验证
2. 不能因为 first_seen_at=今天 就把历史页面放进本期候选
3. Nemo (updated_at=2026-07-09) 继续正确进入 docs_pending
4. 旧页面 (updated_at=2026-01) 正确进入 outside_window
"""
import json
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from urllib.parse import urlparse

from services.official_update_normalizer import OfficialUpdateItem
from services.docs_page_role_classifier import HIGH_VALUE_ROLES

_CAT_OPTIONS = ["产品与功能", "生态与集成", "市场与运营", "待评估"]


def _get_week_id() -> str:
    today = date.today()
    iso = today.isocalendar()
    return f"{iso.year}-W{iso.week:02d}"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _fallback_title(title: str, source_url: str) -> str:
    if title and title.strip():
        return title.strip()
    if source_url:
        path = urlparse(source_url).path.rstrip("/")
        segment = path.split("/")[-1] if path else ""
        if segment:
            return segment.replace("-", " ").replace("_", " ").title()
    return "（无标题）"


def item_to_record(item: OfficialUpdateItem, user_edits: dict = None) -> dict:
    """OfficialUpdateItem → competitor_updates 表插入 dict。"""
    edits = user_edits or {}
    publish_date = item.published_at or item.updated_at or item.update_date or ""
    evidence = getattr(item, "evidence_urls", []) or []
    commit_url = json.dumps(evidence[:3], ensure_ascii=False) if evidence else ""
    title = _fallback_title(getattr(item, "update_title", ""), getattr(item, "source_url", ""))

    record = {
        "competitor":            item.competitor,
        "title":                 title,
        "publish_date":          publish_date,
        "source_url":            item.source_url or "",
        "source_platform":       item.source_channel or "",
        "source_mode":           "official_monitor",
        "summary":               edits.get("summary", item.summary or ""),
        "category":              edits.get("category", item.category or "待评估"),
        "priority":              edits.get("priority", item.importance or "medium"),
        "querit_status":         edits.get("querit_status", item.querit_relevance or ""),
        "review_status":         "待审核",
        "fetch_status":          "pending",
        "discovery_method":      item.discovery_method or "official_direct",
        "analysis_reason":       item.update_status or "",
        "commit_or_release_url": commit_url,
        "secondary_tags":        getattr(item, "docs_page_role", "") or "",
        "collected_at":          _now_iso(),
        "week_id":               _get_week_id(),
    }
    if hasattr(item, "is_entry_page"):
        record["is_entry_page"] = 1 if item.is_entry_page else 0
    return record


# ── 时间判断工具 ─────────────────────────────────────────────

def get_docs_effective_date(item) -> tuple[str, str]:
    """获取 Docs 页面的真实来源日期（用于时间窗口判断）。

    优先级：published_at > updated_at > update_date

    严禁使用：first_seen_at / last_seen_at / last_checked_at / collected_at / 当前时间

    Returns:
        (effective_date_str, source_field_name)
    """
    for fname in ("published_at", "updated_at", "update_date"):
        val = getattr(item, fname, "") or ""
        if val and val.strip():
            return val.strip(), fname
    return "", ""


def _parse_dt(s: str):
    """解析 ISO 日期字符串，返回 timezone-aware datetime，失败返回 None。"""
    if not s:
        return None
    s = s.strip()
    for fmt in (
        "%Y-%m-%dT%H:%M:%SZ",
        "%Y-%m-%dT%H:%M:%S.%fZ",
        "%Y-%m-%dT%H:%M:%S%z",
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d",
    ):
        try:
            d = datetime.strptime(s, fmt)
            if d.tzinfo is None:
                d = d.replace(tzinfo=timezone.utc)
            return d
        except Exception:
            continue
    try:
        d = datetime.fromisoformat(s.replace("Z", "+00:00"))
        if d.tzinfo is None:
            d = d.replace(tzinfo=timezone.utc)
        return d
    except Exception:
        return None


def _is_date_within_window(date_str: str, window_start: str, window_end: str) -> bool:
    """判断日期字符串是否在时间窗口内（含边界）。"""
    dt = _parse_dt(date_str)
    ws = _parse_dt(window_start)
    we = _parse_dt(window_end)
    if dt is None or ws is None or we is None:
        return False
    return ws <= dt <= we


# ── 主结果过滤 ────────────────────────────────────────────────

@dataclass
class DebugItem:
    title: str = ""
    source_url: str = ""
    source_channel: str = ""
    docs_page_role: str = ""
    update_status: str = ""
    published_at: str = ""
    updated_at: str = ""
    update_date: str = ""
    effective_date: str = ""
    effective_date_source: str = ""
    within_window: bool = False
    is_generic_page: bool = False
    import_eligible: bool = True
    bucket: str = ""
    drop_reason: str = ""


@dataclass
class FilterResult:
    blog_valid:     list = field(default_factory=list)
    docs_valid:     list = field(default_factory=list)
    docs_pending:   list = field(default_factory=list)
    github_valid:   list = field(default_factory=list)
    outside_window: list = field(default_factory=list)
    metadata_only:  list = field(default_factory=list)
    generic_page:   list = field(default_factory=list)
    debug_items:    list = field(default_factory=list)   # list[DebugItem]


def filter_valid_results(
    website_items: list,
    github_items: list,
    window_start: str = "",
    window_end: str = "",
) -> FilterResult:
    """按主结果过滤规则分组 OfficialUpdateItem。

    Docs 分桶规则：
    - docs_valid:   effective_date 在窗口内 AND status in (new_page, substantive_update) AND not generic
    - docs_pending: high_value role AND status in (first_seen, new_page, unknown, "")
                    AND effective_date 在窗口内
                    （effective_date 必须是页面真实日期，不能是 first_seen_at）
    - metadata_only: status in (metadata_only, navigation_update, unchanged)
    - generic_page: is_generic_page=True
    - outside_window: effective_date 在窗口外，或无法判断
    """
    result = FilterResult()

    for item in website_items:
        channel = item.source_channel or ""
        status = item.update_status or ""
        is_generic = getattr(item, "is_generic_page", False)
        is_entry = getattr(item, "is_entry_page", False)
        within_win = getattr(item, "within_window", False)
        role = getattr(item, "docs_page_role", "generic") or "generic"

        # 获取 effective_date（来自 item 真实来源日期）
        eff_date, eff_source = get_docs_effective_date(item)

        dbg = DebugItem(
            title=getattr(item, "update_title", ""),
            source_url=getattr(item, "source_url", ""),
            source_channel=channel,
            docs_page_role=role,
            update_status=status,
            published_at=getattr(item, "published_at", ""),
            updated_at=getattr(item, "updated_at", ""),
            update_date=getattr(item, "update_date", ""),
            effective_date=eff_date,
            effective_date_source=eff_source,
            within_window=within_win,
            is_generic_page=is_generic,
            import_eligible=getattr(item, "import_eligible", True),
        )

        # 入口页跳过
        if is_entry:
            dbg.bucket = "dropped"
            dbg.drop_reason = "is_entry_page=True"
            result.debug_items.append(dbg)
            continue

        # Blog
        if channel == "website_blog":
            if within_win:
                result.blog_valid.append(item)
                dbg.bucket = "blog_valid"
            else:
                result.outside_window.append(item)
                dbg.bucket = "outside_window"
                dbg.drop_reason = f"within_window=False (blog published_at={dbg.published_at})"
            result.debug_items.append(dbg)
            continue

        # Docs / Integration
        if channel in ("website_docs", "website_integration"):
            if is_generic:
                result.generic_page.append(item)
                dbg.bucket = "generic_page"
                dbg.drop_reason = f"is_generic_page=True role={role}"
                result.debug_items.append(dbg)
                continue

            if status in ("metadata_only", "navigation_update", "unchanged"):
                result.metadata_only.append(item)
                dbg.bucket = "metadata_only"
                result.debug_items.append(dbg)
                continue

            # 时间窗口验证：使用 effective_date（页面真实日期），不使用 first_seen_at
            if window_start and window_end and eff_date:
                eff_in_window = _is_date_within_window(eff_date, window_start, window_end)
            else:
                # 没有 window 参数时回退到 within_window 字段（向后兼容）
                eff_in_window = within_win

            # docs_valid: 页面真实日期在窗口 + 内容确认变化
            if eff_in_window and status in ("new_page", "substantive_update"):
                result.docs_valid.append(item)
                dbg.bucket = "docs_valid"
                result.debug_items.append(dbg)
                continue

            # docs_pending: 高价值 role + 页面真实日期在窗口 + status 允许不确定
            if eff_in_window and role in HIGH_VALUE_ROLES and status in ("first_seen", "new_page", "unknown", "", "docs_pending_confirmation"):
                result.docs_pending.append(item)
                dbg.bucket = "docs_pending"
                result.debug_items.append(dbg)
                continue

            # 有效日期在窗口但 status 是其他情况 → outside（历史快照不确认）
            # 有效日期在窗口外 → outside
            result.outside_window.append(item)
            dbg.bucket = "outside_window"
            if eff_date and window_start and window_end:
                dbg.drop_reason = (
                    f"source_date_outside_window: eff_date={eff_date[:10]} "
                    f"window={window_start}~{window_end} "
                    f"status={status} role={role}"
                )
            else:
                dbg.drop_reason = (
                    f"no_window_params_or_no_date: eff_date={eff_date!r} "
                    f"status={status} role={role} within_window={within_win}"
                )
            result.debug_items.append(dbg)
            continue

        # 其他来源
        if not within_win:
            result.outside_window.append(item)
            dbg.bucket = "outside_window"
        result.debug_items.append(dbg)

    for item in github_items:
        channel = item.source_channel or ""
        if channel in ("github_commit_group", "github_release"):
            result.github_valid.append(item)

    return result
