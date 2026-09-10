"""测试：重新抓取并更新已有记录"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
from unittest.mock import patch


@pytest.fixture(autouse=True)
def isolated_db(tmp_path, monkeypatch):
    import config, database
    tmp_db = tmp_path / "refetch_test.db"
    monkeypatch.setattr(config, "DB_PATH", tmp_db)
    monkeypatch.setattr(database, "DB_PATH", tmp_db)
    database.init_db()
    database.migrate_db()
    yield


def _insert_failed(url):
    """插入一条抓取失败、URL 即标题的记录，模拟旧测试记录。"""
    import database
    from services.url_normalizer import normalize_url
    from datetime import datetime, timezone
    now = datetime.now(timezone.utc).isoformat()
    database.insert_record({
        "source_url": url,
        "normalized_url": normalize_url(url),
        "title": url,  # 旧失败记录标题为 URL 本身
        "competitor": "Tavily",
        "source_platform": "Blog",
        "fetch_status": "failed",
        "fetch_error": "ConnectTimeout: ...",
        "review_status": "待审核",
        "summary": "人工填写的摘要",
        "business_value": "重要业务价值",
        "querit_status": "待评估",
        "priority": "高",
        "collected_at": now,
        "updated_at": now,
    })
    # 取回 ID
    import database as db
    with db._get_conn() as conn:
        row = conn.execute("SELECT id FROM competitor_updates WHERE source_url=?", (url,)).fetchone()
    return row[0]


def _mock_success_fetch(url):
    from services.url_fetcher import FetchResult
    return FetchResult(
        url=url, final_url=url, status="success",
        title="What keyless search really means for your data | Tavily Blog",
        description="Real meaning of keyless search.",
        published_date="2026-07-10",
        content_snippet="This article explores keyless search.",
        content_source="og",
    )


def _mock_failed_fetch(url):
    from services.url_fetcher import FetchResult
    return FetchResult(url=url, status="failed", error="ConnectTimeout: still failing")


def test_refetch_success_updates_fetch_fields():
    """重新抓取成功后，抓取字段被更新。"""
    import database
    from services.data_service import refetch_and_update

    url = "https://www.tavily.com/blog/keyless"
    rec_id = _insert_failed(url)

    with patch("services.url_fetcher.fetch_url", side_effect=_mock_success_fetch):
        res = refetch_and_update(rec_id, url)

    assert res["status"] == "success"

    updated = database.get_records()[0]
    assert updated["fetch_status"] == "success"
    assert updated["raw_title"] is not None
    assert "Tavily" in (updated["raw_title"] or "")


def test_refetch_does_not_increase_row_count():
    """重新抓取不增加数据库行数。"""
    import database
    from services.data_service import refetch_and_update

    url = "https://www.tavily.com/blog/no-new-row"
    rec_id = _insert_failed(url)
    count_before = len(database.get_records())

    with patch("services.url_fetcher.fetch_url", side_effect=_mock_success_fetch):
        refetch_and_update(rec_id, url)

    assert len(database.get_records()) == count_before


def test_refetch_does_not_overwrite_protected_fields():
    """重新抓取不覆盖人工填写的 summary、business_value、querit_status、priority。"""
    import database
    from services.data_service import refetch_and_update

    url = "https://www.tavily.com/blog/protected"
    rec_id = _insert_failed(url)

    with patch("services.url_fetcher.fetch_url", side_effect=_mock_success_fetch):
        refetch_and_update(rec_id, url)

    updated = database.get_records()[0]
    assert updated["summary"] == "人工填写的摘要"
    assert updated["business_value"] == "重要业务价值"
    assert updated["querit_status"] == "待评估"
    assert updated["priority"] == "高"


def test_refetch_failure_preserves_existing_fields():
    """重新抓取失败时，不清空已有字段。"""
    import database
    from services.data_service import refetch_and_update

    url = "https://www.tavily.com/blog/fail-preserve"
    rec_id = _insert_failed(url)

    with patch("services.url_fetcher.fetch_url", side_effect=_mock_failed_fetch):
        res = refetch_and_update(rec_id, url)

    assert res["status"] == "failed"

    updated = database.get_records()[0]
    # 人工字段保留
    assert updated["summary"] == "人工填写的摘要"
    assert updated["priority"] == "高"
    # fetch_status 更新为失败
    assert updated["fetch_status"] == "failed"


def test_refetch_updates_title_only_when_empty():
    """只有原 title 为空（或等于 URL）时才更新 title。"""
    import database
    from services.data_service import refetch_and_update
    from datetime import datetime, timezone

    url = "https://www.tavily.com/blog/title-update"
    rec_id = _insert_failed(url)  # 旧记录 title = url 本身

    with patch("services.url_fetcher.fetch_url", side_effect=_mock_success_fetch):
        refetch_and_update(rec_id, url)

    updated = database.get_records()[0]
    # 原 title == url，应更新为抓取到的标题
    assert updated["title"] != url
    assert "keyless" in updated["title"].lower()
