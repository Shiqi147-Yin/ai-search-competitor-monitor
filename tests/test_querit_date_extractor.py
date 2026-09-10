"""测试：Querit 日期提取器（支持 camelCase + 嵌套字段）"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from services.publish_date_parser import parse_from_querit_metadata


def test_top_level_published_date():
    """顶层 published_date（snake_case）"""
    r = parse_from_querit_metadata({"published_date": "2026-07-15T10:00:00Z"})
    assert r.date_status == "verified"
    assert "2026-07-15" in r.published_at


def test_camelcase_published_at():
    """camelCase publishedAt"""
    r = parse_from_querit_metadata({"publishedAt": "2026-07-15T10:00:00Z"})
    assert r.date_status == "verified"
    assert "2026-07-15" in r.published_at


def test_page_age_field():
    """Querit 真实字段 page_age"""
    r = parse_from_querit_metadata({"page_age": "2026-07-14T08:00:00Z"})
    assert r.date_status == "verified"
    assert "2026-07-14" in r.published_at


def test_nested_metadata_published_at():
    """metadata.publishedAt 嵌套字段"""
    r = parse_from_querit_metadata({"metadata": {"publishedAt": "2026-07-13T00:00:00Z"}})
    assert r.date_status == "verified"
    assert "2026-07-13" in r.published_at


def test_nested_document_date():
    """document.date 嵌套字段"""
    r = parse_from_querit_metadata({"document": {"date": "2026-07-12"}})
    assert r.date_status == "verified"
    assert "2026-07-12" in r.published_at


def test_unix_timestamp_seconds():
    """秒级 Unix 时间戳"""
    r = parse_from_querit_metadata({"timestamp": "1752652800"})
    assert r.date_status == "verified"


def test_no_date_returns_missing():
    """无日期字段 → missing"""
    r = parse_from_querit_metadata({"title": "no date here"})
    assert r.date_status == "missing"


def test_does_not_use_collected_at():
    """不使用 collected_at 作为发布时间"""
    r = parse_from_querit_metadata({"collected_at": "2026-07-20T00:00:00Z"})
    assert r.date_status == "missing"


def test_does_not_use_fetched_at():
    """不使用 fetched_at"""
    r = parse_from_querit_metadata({"fetched_at": "2026-07-20T00:00:00Z"})
    assert r.date_status == "missing"


def test_published_date_two_ds():
    """适配器字段名修复后：published_date（两个 d）能被正确识别"""
    r = parse_from_querit_metadata({"published_date": "2026-07-18"})
    assert r.date_status == "verified"
    assert "2026-07-18" in r.published_at
