"""测试：新鲜度过滤"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from datetime import datetime, timezone, timedelta
from services.freshness_filter import check_freshness, compute_window


def _ref() -> datetime:
    return datetime(2026, 7, 21, 12, 0, 0, tzinfo=timezone.utc)


def _rec(page_age: str, url="https://example.com", title=""):
    return {"page_age": page_age, "source_url": url, "title": title}


def test_within_7day_window():
    """7天内的结果标记 within_window。"""
    rec = _rec("2026-07-18T10:00:00Z")
    r = check_freshness(rec, 7, _ref())
    assert r.freshness_status == "within_window"
    assert r.should_default_select is True


def test_boundary_date_within():
    """边界日期（恰好 7 天前 + 1 秒内）应保留在窗口内。"""
    # ref = 2026-07-21 12:00:00 UTC, window_start = 2026-07-14 12:00:00 UTC
    # 发布时间 = 2026-07-14 12:00:01 UTC → within
    rec = _rec("2026-07-14T12:00:01Z")
    r = check_freshness(rec, 7, _ref())
    assert r.freshness_status == "within_window"


def test_boundary_date_at_exact_start():
    """恰好等于 window_start 应保留（>= 边界）。"""
    # window_start = 2026-07-14 12:00:00 UTC
    rec = _rec("2026-07-14T12:00:00Z")
    r = check_freshness(rec, 7, _ref())
    assert r.freshness_status == "within_window"


def test_just_before_boundary_outside():
    """比 window_start 早 1 秒 → outside_window。"""
    rec = _rec("2026-07-14T11:59:59Z")
    r = check_freshness(rec, 7, _ref())
    assert r.freshness_status == "outside_window"


def test_8_days_ago_outside():
    """8 天前超出窗口。"""
    rec = _rec("2026-07-13T00:00:00Z")
    r = check_freshness(rec, 7, _ref())
    assert r.freshness_status == "outside_window"
    assert r.should_default_select is False


def test_future_date():
    """发布时间晚于检索时间 → future_date。"""
    rec = _rec("2026-07-22T00:00:00Z")
    r = check_freshness(rec, 7, _ref())
    assert r.freshness_status == "future_date"
    assert r.should_default_select is False


def test_missing_date():
    """无发布时间 → date_missing，不默认勾选。"""
    rec = {"source_url": "https://example.com", "title": "No date"}
    r = check_freshness(rec, 7, _ref())
    assert r.freshness_status == "date_missing"
    assert r.should_default_select is False


def test_2025_result_outside_window():
    """2025 年结果在 7 天窗口内应为 outside_window。"""
    rec = _rec("2025-12-01T00:00:00Z")
    r = check_freshness(rec, 7, _ref())
    assert r.freshness_status == "outside_window"


def test_timezone_aware():
    """UTC+8 时区时间正确换算。"""
    rec = _rec("2026-07-18T02:00:00+08:00")
    r = check_freshness(rec, 7, _ref())
    assert r.freshness_status == "within_window"


def test_window_computation():
    """窗口计算：end = ref_time, start = end - days。"""
    ref = datetime(2026, 7, 21, 0, 0, 0, tzinfo=timezone.utc)
    start, end = compute_window(7, ref)
    assert start.date().isoformat() == "2026-07-14"
    assert end == ref
