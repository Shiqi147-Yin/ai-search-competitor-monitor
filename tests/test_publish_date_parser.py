"""测试：发布时间解析"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from services.publish_date_parser import (
    parse_from_querit_metadata, parse_from_url, parse_from_title,
    parse_published_date,
)


def test_iso8601_z():
    r = parse_from_querit_metadata({"page_age": "2026-07-15T10:00:00Z"})
    assert r.date_status == "verified"
    assert "2026-07-15" in r.published_at


def test_date_only_string():
    r = parse_from_querit_metadata({"published_date": "2026-07-10"})
    assert r.date_status == "verified"
    assert "2026-07-10" in r.published_at


def test_unix_timestamp():
    r = parse_from_querit_metadata({"timestamp": "1752652800"})
    assert r.date_status == "verified"
    assert r.published_at is not None


def test_invalid_date_string():
    r = parse_from_querit_metadata({"published_date": "not-a-date"})
    assert r.date_status == "invalid"


def test_missing_date():
    r = parse_from_querit_metadata({})
    assert r.date_status == "missing"


def test_url_date_extraction():
    r = parse_from_url("https://tavily.com/blog/2026/07/15/announcement")
    assert r.date_status == "inferred"
    assert r.date_source == "url"
    assert "2026-07-15" in r.published_at


def test_title_date_extraction():
    r = parse_from_title("Tavily releases streaming API on July 15, 2026")
    assert r.date_status == "inferred"
    assert r.date_source == "title"
    assert "2026" in r.published_at


def test_github_date_field():
    r = parse_from_querit_metadata({"published_at": "2026-07-14T08:00:00Z"})
    assert r.date_status == "verified"
    assert "2026-07-14" in r.published_at


def test_does_not_use_collected_at():
    """不使用收录时间代替发布时间。"""
    r = parse_published_date(
        {"collected_at": "2026-07-20T00:00:00Z"},  # 只有收录时间
        url="", title="",
    )
    assert r.date_status == "missing"


def test_priority_querit_over_url():
    """Querit metadata 优先于 URL 日期。"""
    r = parse_published_date(
        {"page_age": "2026-07-15T00:00:00Z"},
        url="https://example.com/2025/01/01/article",
    )
    assert "2026-07-15" in r.published_at
    assert r.date_source == "querit_metadata"
