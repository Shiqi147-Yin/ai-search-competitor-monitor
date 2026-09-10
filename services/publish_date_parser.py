"""发布时间解析服务
统一解析来自 Querit API、网页元数据、GitHub、URL/标题中的日期。
"""
import re
from dataclasses import dataclass
from datetime import datetime, timezone, timedelta
from typing import Optional


@dataclass
class ParsedDate:
    published_at: Optional[str] = None        # ISO 8601 UTC
    date_status: str = "missing"              # verified|inferred|missing|invalid
    date_source: str = "none"                 # querit_metadata|web_metadata|github|url|title|none
    date_confidence: float = 0.0
    raw_date: str = ""


# 常见日期格式正则（按置信度排序）
_ISO_PATTERNS = [
    # ISO 8601 with timezone
    r"\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:?\d{2})?",
    # Date only
    r"\d{4}-\d{2}-\d{2}",
]

_URL_DATE_PATTERN = re.compile(r"/(\d{4})/(\d{2})/(\d{2})/")
_TITLE_DATE_PATTERN = re.compile(
    r"\b(\d{4})[-/](\d{2})[-/](\d{2})\b|"
    r"\b(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]* (\d{1,2}),? (\d{4})\b",
    re.IGNORECASE,
)

_MONTH_MAP = {
    "jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
    "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12,
}


def _to_utc_iso(dt: datetime) -> str:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _try_parse_datetime(raw: str) -> Optional[datetime]:
    """尝试解析各种日期字符串。"""
    if not raw:
        return None
    raw = raw.strip()

    # Unix timestamp (int or float as string)
    if re.match(r"^\d{10,13}$", raw):
        try:
            ts = int(raw) / (1000 if len(raw) == 13 else 1)
            return datetime.fromtimestamp(ts, tz=timezone.utc)
        except Exception:
            pass

    # Try common formats
    formats = [
        "%Y-%m-%dT%H:%M:%SZ",
        "%Y-%m-%dT%H:%M:%S.%fZ",
        "%Y-%m-%dT%H:%M:%S%z",
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d",
        "%d/%m/%Y",
        "%m/%d/%Y",
    ]
    for fmt in formats:
        try:
            dt = datetime.strptime(raw[:len(fmt) + 6], fmt)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt
        except Exception:
            continue

    return None


def _extract_date_from_dict(d: dict, depth: int = 0) -> Optional[tuple[str, str]]:
    """递归提取字典中最可能是发布时间的字段值。
    返回 (raw_value, field_path) 或 None。
    只搜索顶层和一层嵌套（metadata, source, document, webpage）。
    严格禁止 collected_at / fetched_at / search_started_at 等收录时间。
    """
    DATE_FIELDS = (
        "published_date", "publishedDate", "published_at", "publishedAt",
        "date", "timestamp", "page_age", "pageAge",
        "publication_date", "publicationDate",
        "last_updated", "lastUpdated",
        "updated_at", "updatedAt",
        "created_at", "createdAt",
    )
    # 禁止使用的收录/系统时间字段
    FORBIDDEN_FIELDS = {
        "collected_at", "fetched_at", "search_started_at",
        "crawled_at", "indexed_at", "imported_at",
    }

    for field in DATE_FIELDS:
        if field in FORBIDDEN_FIELDS:
            continue
        val = d.get(field)
        if val and str(val).strip():
            return str(val).strip(), field

    # 一层嵌套：metadata / source / document / webpage
    if depth == 0:
        for sub_key in ("metadata", "source", "document", "webpage", "raw_metadata"):
            sub = d.get(sub_key)
            if isinstance(sub, dict):
                result = _extract_date_from_dict(sub, depth=1)
                if result:
                    raw_val, path = result
                    return raw_val, f"{sub_key}.{path}"

    return None


def parse_from_querit_metadata(record: dict) -> ParsedDate:
    """从 Querit API 返回字段解析发布时间，支持 camelCase 和嵌套字段。"""
    extracted = _extract_date_from_dict(record)
    if extracted:
        raw_str, field_path = extracted
        dt = _try_parse_datetime(raw_str)
        if dt:
            return ParsedDate(
                published_at=_to_utc_iso(dt),
                date_status="verified",
                date_source="querit_metadata",
                date_confidence=0.9,
                raw_date=raw_str,
            )
        return ParsedDate(
            date_status="invalid",
            date_source="querit_metadata",
            date_confidence=0.0,
            raw_date=raw_str,
        )
    return ParsedDate(date_status="missing", date_source="none")


def parse_from_url(url: str) -> ParsedDate:
    """从 URL 路径提取日期（低置信度）。"""
    if not url:
        return ParsedDate(date_status="missing", date_source="none")
    m = _URL_DATE_PATTERN.search(url)
    if m:
        raw = f"{m.group(1)}-{m.group(2)}-{m.group(3)}"
        dt = _try_parse_datetime(raw)
        if dt:
            return ParsedDate(
                published_at=_to_utc_iso(dt),
                date_status="inferred",
                date_source="url",
                date_confidence=0.5,
                raw_date=raw,
            )
    return ParsedDate(date_status="missing", date_source="none")


def parse_from_title(title: str) -> ParsedDate:
    """从标题中提取日期（低置信度兜底）。"""
    if not title:
        return ParsedDate(date_status="missing", date_source="none")
    m = _TITLE_DATE_PATTERN.search(title)
    if m:
        if m.group(1):  # YYYY-MM-DD or YYYY/MM/DD
            raw = f"{m.group(1)}-{m.group(2)}-{m.group(3)}"
        else:  # Month DD, YYYY
            month = _MONTH_MAP.get(m.group(4)[:3].lower(), 0)
            if not month:
                return ParsedDate(date_status="missing", date_source="none")
            raw = f"{m.group(6)}-{month:02d}-{int(m.group(5)):02d}"
        dt = _try_parse_datetime(raw)
        if dt:
            return ParsedDate(
                published_at=_to_utc_iso(dt),
                date_status="inferred",
                date_source="title",
                date_confidence=0.3,
                raw_date=raw,
            )
    return ParsedDate(date_status="missing", date_source="none")


def parse_published_date(
    record: dict,
    url: str = "",
    title: str = "",
) -> ParsedDate:
    """按优先级解析发布时间。

    优先级：
    1. Querit metadata 字段（page_age、published_date 等）
    2. URL 中的日期
    3. 标题中的日期
    """
    # 优先级 1：Querit/API metadata
    result = parse_from_querit_metadata(record)
    if result.date_status in ("verified", "inferred"):
        return result

    # 优先级 2：URL
    url_result = parse_from_url(url or record.get("source_url", ""))
    if url_result.date_status == "inferred":
        return url_result

    # 优先级 3：标题
    title_result = parse_from_title(title or record.get("title", ""))
    if title_result.date_status == "inferred":
        return title_result

    return ParsedDate(date_status="missing", date_source="none")
