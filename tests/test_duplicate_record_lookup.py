"""测试：重复记录查询与展示"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest


@pytest.fixture(autouse=True)
def isolated_db(tmp_path, monkeypatch):
    import config, database
    tmp_db = tmp_path / "dup_test.db"
    monkeypatch.setattr(config, "DB_PATH", tmp_db)
    monkeypatch.setattr(database, "DB_PATH", tmp_db)
    database.init_db()
    database.migrate_db()
    yield


def _insert(url, competitor="Tavily", platform="Blog", title="Test Title",
             fetch_status="success"):
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


def test_duplicate_returns_existing_record():
    """重复 URL 返回数据库中已有记录，不返回 None。"""
    import database
    from services.url_normalizer import normalize_url

    url = "https://tavily.com/blog/test"
    _insert(url, competitor="Tavily", platform="Blog")

    existing = database.get_record_by_url(normalize_url(url))
    assert existing is not None
    assert existing["id"] > 0


def test_duplicate_returns_real_competitor_not_other():
    """重复记录返回真实 competitor，不返回默认 Other。"""
    import database
    from services.url_normalizer import normalize_url

    url = "https://tavily.com/blog/real"
    _insert(url, competitor="Tavily", platform="Blog")

    existing = database.get_record_by_url(normalize_url(url))
    assert existing["competitor"] == "Tavily"
    assert existing["source_platform"] == "Blog"


def test_duplicate_does_not_add_new_row():
    """重复 URL 查询不增加数据库行数。"""
    import database
    from services.url_normalizer import normalize_url

    url = "https://tavily.com/blog/no-new-row"
    _insert(url)

    before = database.get_records()
    count_before = len(before)

    # 再次查询（不插入）
    database.get_record_by_url(normalize_url(url))

    after = database.get_records()
    assert len(after) == count_before


def test_duplicate_returns_record_id():
    """返回的已有记录包含有效 duplicate_record_id。"""
    import database
    from services.url_normalizer import normalize_url
    from unittest.mock import patch
    from services.import_batch_service import process_url_list

    url = "https://exa.ai/blog/dup-id-test"
    _insert(url, competitor="Exa", platform="Blog")

    with patch("services.import_batch_service.fetch_url") as mock_fetch:
        from services.url_fetcher import FetchResult
        mock_fetch.return_value = FetchResult(url=url, status="success", title="T")
        results = process_url_list([url])

    dup = [r for r in results if r.is_duplicate]
    assert len(dup) == 1
    assert dup[0].duplicate_record_id > 0


def test_duplicate_shows_real_fields_not_other():
    """重复时预览层 competitor/source_platform 不再显示 Other/Other。"""
    import database
    from services.url_normalizer import normalize_url
    from unittest.mock import patch
    from services.import_batch_service import process_url_list

    url = "https://docs.tavily.com/documentation/integrations/test"
    _insert(url, competitor="Tavily", platform="官网")

    with patch("services.import_batch_service.fetch_url") as mock_fetch:
        from services.url_fetcher import FetchResult
        mock_fetch.return_value = FetchResult(url=url, status="success", title="T")
        results = process_url_list([url])

    dup = [r for r in results if r.is_duplicate]
    assert dup[0].competitor == "Tavily"
    assert dup[0].source_platform == "官网"
