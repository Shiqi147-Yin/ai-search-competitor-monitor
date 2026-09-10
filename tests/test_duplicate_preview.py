"""测试：重复记录预览展示逻辑"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
from unittest.mock import patch


@pytest.fixture(autouse=True)
def isolated_db(tmp_path, monkeypatch):
    import config, database
    tmp_db = tmp_path / "preview_test.db"
    monkeypatch.setattr(config, "DB_PATH", tmp_db)
    monkeypatch.setattr(database, "DB_PATH", tmp_db)
    database.init_db()
    database.migrate_db()
    yield


def _insert(url, competitor, platform, fetch_status, title="Test"):
    import database
    from services.url_normalizer import normalize_url
    database.insert_record({
        "source_url": url,
        "normalized_url": normalize_url(url),
        "title": title,
        "competitor": competitor,
        "source_platform": platform,
        "fetch_status": fetch_status,
        "review_status": "待审核",
    })


def _process(url):
    from services.import_batch_service import process_url_list
    from services.url_fetcher import FetchResult
    with patch("services.import_batch_service.fetch_url",
               return_value=FetchResult(url=url, status="success", title="T")):
        return process_url_list([url])


def test_duplicate_shows_existing_status():
    """重复记录预览应展示已有状态，而非空值。"""
    url = "https://tavily.com/blog/preview"
    _insert(url, "Tavily", "Blog", "failed")

    results = _process(url)
    dup = results[0]
    assert dup.is_duplicate
    assert dup.duplicate_fetch_status == "failed"
    assert dup.duplicate_review_status == "待审核"


def test_can_distinguish_complete_vs_failed():
    """可区分信息完整、抓取失败两种已有状态。"""
    url_ok = "https://exa.ai/blog/complete"
    url_fail = "https://exa.ai/blog/failed"
    _insert(url_ok, "Exa", "Blog", "success", title="Exa Post")
    _insert(url_fail, "Exa", "Blog", "failed", title=url_fail)

    r_ok = _process(url_ok)[0]
    r_fail = _process(url_fail)[0]

    assert r_ok.duplicate_fetch_status == "success"
    assert r_fail.duplicate_fetch_status == "failed"


def test_docs_tavily_duplicate_shows_tavily_official():
    """docs.tavily.com 重复记录仍显示 Tavily + 官网。"""
    url = "https://docs.tavily.com/documentation/integrations/nemo-deepagents"
    _insert(url, "Tavily", "官网", "failed")

    results = _process(url)
    dup = results[0]
    assert dup.duplicate_competitor == "Tavily"
    assert dup.duplicate_platform == "官网"
    # 预览层 competitor/source_platform 使用已有记录的值
    assert dup.competitor == "Tavily"
    assert dup.source_platform == "官网"


def test_luma_tavily_duplicate_shows_event():
    """luma.com/tavily-h550 重复记录显示 Tavily + Event。"""
    url = "https://luma.com/tavily-h550"
    # 旧记录是 Other/Event（来源识别当时只识别出平台）
    _insert(url, "Other", "Event", "failed")

    results = _process(url)
    dup = results[0]
    # 旧记录 competitor=Other → 应用 source_detector 补全
    # detect_competitor("https://luma.com/tavily-h550") = "Tavily"
    assert dup.competitor == "Tavily"
    assert dup.source_platform == "Event"
