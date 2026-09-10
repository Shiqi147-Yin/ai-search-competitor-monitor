"""测试：默认选择质量"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from datetime import datetime, timezone
from services.freshness_filter import check_freshness
from services.competitor_relevance_filter import classify_relevance


def _ref():
    return datetime(2026, 7, 21, 0, 0, 0, tzinfo=timezone.utc)


def _should_select(url, published_date, competitor="Tavily",
                   match_type="domain_keyword", match_score=0.8, is_dup=False):
    rec = {"source_url": url, "published_date": published_date, "title": "Test"}
    fr = check_freshness(rec, 7, _ref())
    rel = classify_relevance(rec, competitor, match_type, match_score)
    return (
        fr.freshness_status == "within_window" and
        not is_dup and
        rel["official_source"] and
        rel["target_match_status"] in ("exact_target", "likely_target")
    )


def test_official_within_window_high_relevance_selected():
    """官方 + 窗口内 + 高相关 → 默认选择"""
    assert _should_select(
        "https://tavily.com/blog/keyless", "2026-07-18T00:00:00Z",
        match_type="exact_url", match_score=1.0
    ) is True


def test_third_party_within_window_not_selected():
    """第三方 + 窗口内 → 默认不选"""
    assert _should_select(
        "https://advfn.com/news/tavily", "2026-07-18T00:00:00Z",
        match_type="no_match", match_score=0.0
    ) is False


def test_official_outside_window_not_selected():
    """官方但超期 → 默认不选"""
    assert _should_select(
        "https://tavily.com/blog/old", "2025-01-01T00:00:00Z",
        match_type="exact_url", match_score=1.0
    ) is False


def test_official_date_missing_not_selected():
    """官方但日期缺失 → freshness=date_missing → 默认不选"""
    assert _should_select(
        "https://tavily.com/blog/nodoc", "",
        match_type="exact_url", match_score=1.0
    ) is False


def test_advfn_not_selected():
    """ADVFN 聚合页 → low_value + no_match → 不选"""
    assert _should_select(
        "https://advfn.com/news/abc", "2026-07-19T00:00:00Z",
        match_type="no_match", match_score=0.0
    ) is False


def test_duplicate_not_selected():
    """重复记录 → 不选"""
    assert _should_select(
        "https://tavily.com/blog/keyless", "2026-07-18T00:00:00Z",
        match_type="exact_url", match_score=1.0,
        is_dup=True
    ) is False
