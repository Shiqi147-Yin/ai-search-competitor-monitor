"""英文 Query 生成器（分来源定向版）
从 YAML 模板生成面向 Querit API 的英文搜索 Query。
所有 Query 必须为英文，不得使用中文。
All 模式拆为多个来源 Query，避免宽泛检索被聚合页占用。
"""
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Optional
import yaml

_TEMPLATES_PATH = Path(__file__).parent.parent / "config" / "querit_query_templates.yaml"
_SOURCES_PATH = Path(__file__).parent.parent / "config" / "competitor_sources.yaml"

_MONTH_NAMES = [
    "January", "February", "March", "April", "May", "June",
    "July", "August", "September", "October", "November", "December",
]


def _load_templates() -> dict:
    try:
        with open(_TEMPLATES_PATH, encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    except Exception:
        return {}


def _load_sources(competitor: str) -> dict:
    try:
        with open(_SOURCES_PATH, encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
        return data.get(competitor, {})
    except Exception:
        return {}


def _get_source_query_types(source_scope: list[str]) -> list[str]:
    data = _load_templates()
    mapping = data.get("source_scope_mapping", {})
    types: list[str] = []
    for src in source_scope:
        for qt in mapping.get(src, []):
            if qt not in types:
                types.append(qt)
    return types


def _format_date_range(time_window_days: int, reference_time: Optional[datetime] = None) -> dict:
    end = reference_time or datetime.now(timezone.utc)
    start = end - timedelta(days=time_window_days)

    def _fmt(dt: datetime) -> str:
        return f"{_MONTH_NAMES[dt.month - 1]} {dt.day}, {dt.year}"

    return {
        "start_date": _fmt(start),
        "end_date": _fmt(end),
        "start_iso": start.strftime("%Y-%m-%d"),
        "end_iso": end.strftime("%Y-%m-%d"),
    }


def _resolve_template_vars(template: str, competitor: str, time_window_days: int,
                            date_range: dict, competitor_sources: dict) -> str:
    """填充模板变量，包括竞品域名、GitHub owner 等。"""
    official_domains = competitor_sources.get("official_domains", [])
    docs_domain = next((d for d in official_domains if "docs." in d), official_domains[0] if official_domains else "")
    main_domain = official_domains[0] if official_domains else competitor.lower() + ".com"
    github_owners = competitor_sources.get("official_github", {}).get("owners", [])
    github_owner = github_owners[0] if github_owners else competitor.lower()

    result = (
        template
        .replace("{competitor}", competitor)
        .replace("{time_window}", str(time_window_days))
        .replace("{start_date}", date_range["start_date"])
        .replace("{end_date}", date_range["end_date"])
        .replace("{competitor_domain}", main_domain)
        .replace("{competitor_docs_domain}", docs_domain or main_domain)
        .replace("{github_owner}", github_owner)
        .strip()
    )
    return result


def _add_date_range_suffix(query: str, query_type: str, date_range: dict) -> str:
    """为旧式（非定向）模板追加绝对日期范围。"""
    # 定向模板已自带日期，跳过
    if "_targeted" in query_type:
        return query
    start = date_range["start_date"]
    end = date_range["end_date"]
    if query_type in ("github", "github_targeted"):
        suffix = (
            f" Focus on content committed or released between {start} and {end}. "
            f"Exclude content from before {start}."
        )
    elif "event" in query_type:
        suffix = (
            f" Focus on events announced or held between {start} and {end}. "
            f"Exclude older content from before {start}."
        )
    else:
        suffix = (
            f" Prioritize content published between {start} and {end}. "
            f"Exclude older content published before {start}."
        )
    return query.rstrip(".").rstrip() + suffix


def generate_queries(
    competitors: list[str],
    time_window_days: int = 7,
    source_scope: Optional[list[str]] = None,
    reference_time: Optional[datetime] = None,
) -> list[dict]:
    """生成英文 Query 列表，含绝对日期范围和来源定向。
    All 模式默认使用精确来源拆分，不使用单一宽泛 Query。
    """
    if source_scope is None or "All" in source_scope:
        source_scope = ["All"]

    data = _load_templates()
    templates = data.get("templates", {})
    query_types = _get_source_query_types(source_scope)
    if not query_types:
        query_types = ["official_blog_targeted", "official_docs_targeted",
                       "github_targeted", "events_targeted", "social_targeted"]

    date_range = _format_date_range(time_window_days, reference_time)

    results: list[dict] = []
    for competitor in competitors:
        comp_sources = _load_sources(competitor)
        for qt in query_types:
            tpl = templates.get(qt, {})
            template_str = tpl.get("template", "")
            if not template_str:
                continue
            query = _resolve_template_vars(template_str, competitor, time_window_days,
                                           date_range, comp_sources)
            # 旧式模板追加日期
            query = _add_date_range_suffix(query, qt, date_range)

            results.append({
                "generated_query": query,
                "query_type": qt,
                "source_target": tpl.get("source_target", ""),
                "competitor": competitor,
                "source_scope": source_scope,
                "time_window": time_window_days,
                "window_start": date_range["start_iso"],
                "window_end": date_range["end_iso"],
            })
    return results


def is_english_query(query: str) -> bool:
    if not query:
        return False
    ascii_chars = sum(1 for c in query if ord(c) < 128)
    return ascii_chars / len(query) > 0.8
