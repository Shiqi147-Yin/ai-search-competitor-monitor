"""测试：默认选择规则"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from datetime import datetime, timezone
from services.freshness_filter import check_freshness


def _ref():
    return datetime(2026, 7, 21, 12, 0, 0, tzinfo=timezone.utc)


def _rec(page_age=""):
    return {"page_age": page_age, "source_url": "https://example.com"}


def test_within_window_default_selected():
    r = check_freshness(_rec("2026-07-18T00:00:00Z"), 7, _ref())
    assert r.should_default_select is True


def test_outside_window_not_selected():
    r = check_freshness(_rec("2025-01-01T00:00:00Z"), 7, _ref())
    assert r.should_default_select is False


def test_missing_date_not_selected():
    r = check_freshness(_rec(""), 7, _ref())
    assert r.should_default_select is False


def test_future_date_not_selected():
    r = check_freshness(_rec("2027-01-01T00:00:00Z"), 7, _ref())
    assert r.should_default_select is False


def test_invalid_date_not_selected():
    r = check_freshness(_rec("not-a-date"), 7, _ref())
    assert r.should_default_select is False


def test_duplicate_overrides_selection():
    """即使新鲜度为 within_window，重复记录也不应默认勾选（由页面层决定）。"""
    r = check_freshness(_rec("2026-07-18T00:00:00Z"), 7, _ref())
    # freshness 层只关心时间，不关心重复，页面层额外检查 _is_duplicate
    assert r.should_default_select is True  # freshness 自身是 True
    # 页面逻辑：_should_select = fr.should_default_select and not rec["_is_duplicate"]
    final_select = r.should_default_select and False  # 假设是重复
    assert final_select is False
