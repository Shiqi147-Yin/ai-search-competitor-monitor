"""测试：待审核区失败记录重新抓取（成功路径）"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
from unittest.mock import patch


@pytest.fixture(autouse=True)
def isolated_db(tmp_path, monkeypatch):
    import config, database
    tmp_db = tmp_path / "refetch_pending.db"
    monkeypatch.setattr(config, "DB_PATH", tmp_db)
    monkeypatch.setattr(database, "DB_PATH", tmp_db)
    database.init_db()
    database.migrate_db()
    yield


def _insert_failed_pending(url, title=None):
    import database
    from services.url_normalizer import normalize_url
    from datetime import datetime, timezone
    now = datetime.now(timezone.utc).isoformat()
    database.insert_record({
        "source_url": url,
        "normalized_url": normalize_url(url),
        "title": title or url,
        "competitor": "Other",
        "source_platform": "Other",
        "fetch_status": "failed",
        "fetch_error": "ConnectTimeout: ...",
        "review_status": "待审核",
        "summary": "旧摘要",
        "priority": "中",
        "querit_status": "待评估",
        "collected_at": now,
        "updated_at": now,
    })
    import database as db
    with db._get_conn() as conn:
        row = conn.execute("SELECT id FROM competitor_updates WHERE source_url=?", (url,)).fetchone()
    return row[0]


def _success_fetch(url):
    from services.url_fetcher import FetchResult
    return FetchResult(
        url=url, final_url=url, status="success",
        title="What keyless search really means for your data | Tavily Blog",
        description="Desc.", published_date="2026-07-10",
        content_snippet="Article content.", content_source="og",
    )


def test_refetch_pending_success_updates_fetch_status():
    """重新抓取成功后 fetch_status 更新为 success。"""
    import database
    from services.data_service import refetch_and_update

    url = "https://tavily.com/blog/keyless"
    rid = _insert_failed_pending(url)

    with patch("services.url_fetcher.fetch_url", side_effect=_success_fetch):
        res = refetch_and_update(rid, url)

    assert res["status"] == "success"
    updated = database.get_record_by_url(url)
    assert updated["fetch_status"] == "success"


def test_refetch_pending_clears_fetch_error_on_success():
    """重新抓取成功后 fetch_error 清空（为 None 或空字符串）。"""
    import database
    from services.data_service import refetch_and_update

    url = "https://tavily.com/blog/clear-error"
    rid = _insert_failed_pending(url)

    with patch("services.url_fetcher.fetch_url", side_effect=_success_fetch):
        refetch_and_update(rid, url)

    updated = database.get_record_by_url(url)
    assert not updated.get("fetch_error")


def test_refetch_pending_does_not_add_row():
    """重新抓取不新增数据库行数。"""
    import database
    from services.data_service import refetch_and_update

    url = "https://tavily.com/blog/no-add"
    rid = _insert_failed_pending(url)
    count_before = len(database.get_records())

    with patch("services.url_fetcher.fetch_url", side_effect=_success_fetch):
        refetch_and_update(rid, url)

    assert len(database.get_records()) == count_before


def test_refetch_pending_does_not_overwrite_protected_fields():
    """重新抓取不覆盖人工填写的 summary、priority、querit_status。"""
    import database
    from services.data_service import refetch_and_update

    url = "https://tavily.com/blog/protect"
    rid = _insert_failed_pending(url)

    with patch("services.url_fetcher.fetch_url", side_effect=_success_fetch):
        refetch_and_update(rid, url)

    updated = database.get_record_by_url(url)
    assert updated["summary"] == "旧摘要"
    assert updated["priority"] == "中"
    assert updated["querit_status"] == "待评估"
