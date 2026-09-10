"""测试：重新抓取失败路径（ConnectTimeout）"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
from unittest.mock import patch


@pytest.fixture(autouse=True)
def isolated_db(tmp_path, monkeypatch):
    import config, database
    tmp_db = tmp_path / "refetch_fail.db"
    monkeypatch.setattr(config, "DB_PATH", tmp_db)
    monkeypatch.setattr(database, "DB_PATH", tmp_db)
    database.init_db()
    database.migrate_db()
    yield


def _insert(url):
    import database
    from services.url_normalizer import normalize_url
    from datetime import datetime, timezone
    now = datetime.now(timezone.utc).isoformat()
    database.insert_record({
        "source_url": url,
        "normalized_url": normalize_url(url),
        "title": url,
        "competitor": "Tavily",
        "source_platform": "Event",
        "fetch_status": "failed",
        "fetch_error": "ConnectTimeout: previous error",
        "review_status": "待审核",
        "summary": "Event info",
        "priority": "高",
        "collected_at": now,
        "updated_at": now,
    })
    import database as db
    with db._get_conn() as conn:
        row = conn.execute("SELECT id FROM competitor_updates WHERE source_url=?", (url,)).fetchone()
    return row[0]


def _timeout_fetch(url):
    from services.url_fetcher import FetchResult
    return FetchResult(url=url, status="failed", error="ConnectTimeout: still failing")


def test_refetch_timeout_keeps_source_url():
    """ConnectTimeout 时原始 URL 不被清空。"""
    import database
    from services.data_service import refetch_and_update

    url = "https://luma.com/tavily-h550"
    rid = _insert(url)

    with patch("services.url_fetcher.fetch_url", side_effect=_timeout_fetch):
        refetch_and_update(rid, url)

    updated = database.get_record_by_url(url)
    assert updated["source_url"] == url


def test_refetch_timeout_error_contains_connect_timeout():
    """ConnectTimeout 时 fetch_error 包含 ConnectTimeout。"""
    import database
    from services.data_service import refetch_and_update

    url = "https://luma.com/tavily-h550-2"
    rid = _insert(url)

    with patch("services.url_fetcher.fetch_url", side_effect=_timeout_fetch):
        refetch_and_update(rid, url)

    updated = database.get_record_by_url(url)
    assert "ConnectTimeout" in (updated.get("fetch_error") or "")


def test_refetch_timeout_preserves_existing_fields():
    """ConnectTimeout 时不清空已有 summary、priority 等字段。"""
    import database
    from services.data_service import refetch_and_update

    url = "https://luma.com/tavily-h550-3"
    rid = _insert(url)

    with patch("services.url_fetcher.fetch_url", side_effect=_timeout_fetch):
        refetch_and_update(rid, url)

    updated = database.get_record_by_url(url)
    assert updated["summary"] == "Event info"
    assert updated["priority"] == "高"
