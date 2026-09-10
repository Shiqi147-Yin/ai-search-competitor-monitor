"""测试：页面日期字段不再因字段名不一致显示空值"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from services.querit_client import SearchResult
from services.querit_result_adapter import adapt_result
from services.freshness_filter import check_freshness
from datetime import datetime, timezone


def _ref():
    return datetime(2026, 7, 21, 0, 0, 0, tzinfo=timezone.utc)


def test_rec_has_published_date_two_ds():
    """adapt_result 后 rec 包含 published_date（两个 d）"""
    sr = SearchResult(url="https://tavily.com/test", published_date="2026-07-18T10:00:00Z",
                      rank=1, query="test", raw_source="", raw_metadata={})
    rec = adapt_result(sr, "run1", 1)
    assert "published_date" in rec
    assert rec["published_date"] == "2026-07-18T10:00:00Z"


def test_page_display_uses_correct_field():
    """页面 rec.get('published_date') 能读到正确日期"""
    sr = SearchResult(url="https://tavily.com/test2", published_date="2026-07-17T00:00:00Z",
                      rank=1, query="test", raw_source="", raw_metadata={})
    rec = adapt_result(sr, "run1", 1)
    # 模拟页面取值逻辑
    display_date = (rec.get("published_date") or rec.get("publish_date") or "")[:10]
    assert display_date == "2026-07-17"


def test_freshness_result_has_date_after_fix():
    """新鲜度结果有正常 normalized_published_at"""
    sr = SearchResult(url="https://tavily.com/test3", published_date="2026-07-19T00:00:00Z",
                      rank=1, query="test", raw_source="", raw_metadata={})
    rec = adapt_result(sr, "run1", 1)
    fr = check_freshness(rec, 7, _ref())
    assert fr.normalized_published_at != ""
    assert "2026-07-19" in fr.normalized_published_at


def test_no_date_shows_empty_not_error():
    """无发布时间时页面显示为空而非报错"""
    sr = SearchResult(url="https://tavily.com/nodate", published_date="",
                      rank=1, query="test", raw_source="", raw_metadata={})
    rec = adapt_result(sr, "run1", 1)
    fr = check_freshness(rec, 7, _ref())
    display_date = (
        (fr.normalized_published_at or fr.raw_published_date)[:10]
        if fr and (fr.normalized_published_at or fr.raw_published_date)
        else (rec.get("published_date") or rec.get("publish_date") or "")[:10]
    )
    assert display_date == ""  # 空字符串，不是 None 或报错
