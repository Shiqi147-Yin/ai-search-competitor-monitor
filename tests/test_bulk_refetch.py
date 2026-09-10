"""测试：批量重新抓取（success/failed/success 混合）"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
from unittest.mock import patch


@pytest.fixture(autouse=True)
def isolated_db(tmp_path, monkeypatch):
    import config, database
    tmp_db = tmp_path / "bulk_refetch.db"
    monkeypatch.setattr(config, "DB_PATH", tmp_db)
    monkeypatch.setattr(database, "DB_PATH", tmp_db)
    database.init_db()
    database.migrate_db()
    yield


def _insert(url, fetch_status="failed", summary="s", priority="中"):
    import database
    from services.url_normalizer import normalize_url
    from datetime import datetime, timezone
    now = datetime.now(timezone.utc).isoformat()
    database.insert_record({
        "source_url": url,
        "normalized_url": normalize_url(url),
        "title": url,
        "fetch_status": fetch_status,
        "fetch_error": "old error",
        "review_status": "待审核",
        "summary": summary,
        "priority": priority,
        "collected_at": now,
        "updated_at": now,
    })
    import database as db
    with db._get_conn() as conn:
        row = conn.execute("SELECT id FROM competitor_updates WHERE source_url=?", (url,)).fetchone()
    return row[0]


def _make_fetch_side_effect(success_urls):
    """success_urls 中的 URL 返回 success，否则返回 failed。"""
    from services.url_fetcher import FetchResult

    def _fetch(url):
        if url in success_urls:
            return FetchResult(url=url, final_url=url, status="success",
                               title="Title", description="D", content_source="og")
        return FetchResult(url=url, status="failed", error="ConnectTimeout: x")

    return _fetch


def test_bulk_refetch_processes_each_record():
    """批量重新抓取逐条处理所有记录。"""
    import database
    from services.data_service import refetch_and_update

    urls = [
        "https://tavily.com/ok1",
        "https://luma.com/fail",
        "https://docs.tavily.com/ok2",
    ]
    ids = [_insert(u) for u in urls]

    with patch("services.url_fetcher.fetch_url",
               side_effect=_make_fetch_side_effect({urls[0], urls[2]})):
        results = [refetch_and_update(rid, url) for rid, url in zip(ids, urls)]

    statuses = [r["status"] for r in results]
    assert "success" in statuses
    assert "failed" in statuses


def test_bulk_refetch_single_failure_does_not_stop_others():
    """单条失败不影响其他记录被处理。"""
    import database
    from services.data_service import refetch_and_update

    urls = [
        "https://tavily.com/ok-a",
        "https://luma.com/fail-b",
        "https://exa.ai/ok-c",
    ]
    ids = [_insert(u) for u in urls]

    call_count = {"n": 0}

    def _fetch(url):
        call_count["n"] += 1
        if "fail" in url:
            raise Exception("Unexpected exception during fetch")
        from services.url_fetcher import FetchResult
        return FetchResult(url=url, status="success", title="T", content_source="og")

    # 使用 try/except 包裹逐条处理（模拟页面批量逻辑）
    results = []
    with patch("services.url_fetcher.fetch_url", side_effect=_fetch):
        for rid, url in zip(ids, urls):
            try:
                res = refetch_and_update(rid, url)
                results.append(res["status"])
            except Exception:
                results.append("exception_caught")

    assert call_count["n"] == 3   # 三条都被尝试
    assert results.count("success") == 2


def test_bulk_refetch_does_not_add_rows():
    """批量重新抓取不新增数据库行数。"""
    import database
    from services.data_service import refetch_and_update

    urls = ["https://tavily.com/bulk-a", "https://tavily.com/bulk-b"]
    ids = [_insert(u) for u in urls]
    count_before = len(database.get_records())

    with patch("services.url_fetcher.fetch_url",
               side_effect=_make_fetch_side_effect(set(urls))):
        for rid, url in zip(ids, urls):
            refetch_and_update(rid, url)

    assert len(database.get_records()) == count_before


def test_bulk_refetch_statistics_correct():
    """批量重新抓取统计（success/failed）数量正确。"""
    from services.data_service import refetch_and_update

    urls = [
        "https://tavily.com/stat-ok1",
        "https://luma.com/stat-fail",
        "https://docs.tavily.com/stat-ok2",
    ]
    ids = [_insert(u) for u in urls]
    success_n, failed_n = 0, 0

    with patch("services.url_fetcher.fetch_url",
               side_effect=_make_fetch_side_effect({urls[0], urls[2]})):
        for rid, url in zip(ids, urls):
            res = refetch_and_update(rid, url)
            if res["status"] == "success":
                success_n += 1
            elif res["status"] == "failed":
                failed_n += 1

    assert success_n == 2
    assert failed_n == 1
