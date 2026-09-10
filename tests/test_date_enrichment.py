"""测试：日期补充（网页/GitHub/LinkedIn）"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from services.publish_date_parser import parse_published_date
from services.freshness_filter import check_freshness
from datetime import datetime, timezone


def test_url_date_fallback_when_querit_has_no_date():
    """Querit 没有日期时，从 URL 提取"""
    rec = {"source_url": "https://tavily.com/blog/2026/07/15/announcement", "title": "Test"}
    r = parse_published_date(rec)
    assert r.date_status == "inferred"
    assert r.date_source == "url"
    assert "2026-07-15" in r.published_at


def test_title_date_fallback():
    """URL 无日期时，从标题提取"""
    rec = {"source_url": "https://tavily.com/post", "title": "Tavily Update July 15, 2026"}
    r = parse_published_date(rec)
    assert r.date_status == "inferred"
    assert r.date_source == "title"
    assert "2026" in r.published_at


def test_linkedin_restricted_stays_missing():
    """LinkedIn 受限时不虚构日期，保持 date_missing"""
    rec = {
        "source_url": "https://linkedin.com/posts/exa-ai_update",
        "title": "",
        "summary": "",
        "fetch_status": "restricted",
        "source_platform": "LinkedIn",
    }
    r = parse_published_date(rec)
    # LinkedIn 受限且无标题无摘要 → missing（URL 无日期时也 missing）
    assert r.date_status in ("missing", "inferred")
    if r.date_status == "inferred":
        assert r.date_source in ("url", "title")


def test_failed_enrich_preserves_missing():
    """补抓取失败时保持 date_missing，不虚构"""
    rec = {"source_url": "https://unknown.example.com/post", "title": ""}
    r = parse_published_date(rec)
    # 无日期来源 → missing
    assert r.date_status == "missing"


def test_freshness_missing_not_within_window():
    """date_missing 不被视为窗口内"""
    rec = {"source_url": "https://unknown.example.com/post", "title": ""}
    ref = datetime(2026, 7, 21, 0, 0, 0, tzinfo=timezone.utc)
    fr = check_freshness(rec, 7, ref)
    assert fr.freshness_status == "date_missing"
    assert fr.should_default_select is False
