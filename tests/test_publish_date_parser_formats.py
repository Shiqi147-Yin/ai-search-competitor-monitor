"""测试：publish_date_parser 各种日期格式"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from services.publish_date_parser import _try_parse_datetime, parse_from_querit_metadata


def _parse_ok(raw_str: str, expected_year: int, expected_month: int):
    dt = _try_parse_datetime(raw_str)
    assert dt is not None, f"解析失败：{raw_str!r}"
    assert dt.year == expected_year
    assert dt.month == expected_month


def test_iso_z():
    _parse_ok("2026-07-20T16:00:00Z", 2026, 7)


def test_iso_milliseconds():
    _parse_ok("2026-07-20T16:00:00.000Z", 2026, 7)


def test_iso_with_offset():
    _parse_ok("2026-07-20T00:00:00+08:00", 2026, 7)


def test_date_only_string():
    _parse_ok("2026-07-20", 2026, 7)


def test_unix_seconds():
    """秒级时间戳（10位）"""
    import time
    ts_str = "1753056000"  # ~ 2025-07-21
    dt = _try_parse_datetime(ts_str)
    assert dt is not None
    assert dt.year >= 2025


def test_unix_milliseconds():
    """毫秒级时间戳（13位）"""
    ts_str = "1753056000000"
    dt = _try_parse_datetime(ts_str)
    assert dt is not None


def test_date_with_space():
    _parse_ok("2026-07-20 16:00:00", 2026, 7)


def test_parse_from_querit_metadata_iso():
    r = parse_from_querit_metadata({"page_age": "2026-07-15T10:00:00Z"})
    assert r.date_status == "verified"
    assert "2026-07-15" in r.published_at
    assert r.date_source == "querit_metadata"


def test_invalid_returns_none():
    assert _try_parse_datetime("not-a-date") is None
    assert _try_parse_datetime("") is None
    assert _try_parse_datetime(None) is None
