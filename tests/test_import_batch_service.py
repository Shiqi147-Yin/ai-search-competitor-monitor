"""测试：批次服务"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from unittest.mock import patch, MagicMock
import pytest


@pytest.fixture(autouse=True)
def isolated_db(tmp_path, monkeypatch):
    import config, database
    tmp_db = tmp_path / "batch_test.db"
    monkeypatch.setattr(config, "DB_PATH", tmp_db)
    monkeypatch.setattr(database, "DB_PATH", tmp_db)
    database.init_db()
    database.migrate_db()
    yield


def _mock_fetch(url):
    from services.url_fetcher import FetchResult
    if "fail" in url:
        return FetchResult(url=url, status="failed", error="connection error")
    if "restricted" in url:
        return FetchResult(url=url, status="restricted", error="HTTP 403")
    return FetchResult(
        url=url, final_url=url, status="success",
        title=f"Title for {url}", description="desc", published_date="2026-07-01",
        content_snippet="content", content_source="og",
    )


@patch("services.import_batch_service.fetch_url", side_effect=_mock_fetch)
def test_batch_processes_each_url(mock_fetch):
    from services.import_batch_service import process_url_list
    urls = ["https://tavily.com/a", "https://exa.ai/b"]
    results = process_url_list(urls)
    assert len(results) == 2
    assert all(r.fetch_status in ("success", "partial", "failed", "restricted") for r in results)


@patch("services.import_batch_service.fetch_url", side_effect=_mock_fetch)
def test_single_failure_does_not_interrupt_batch(mock_fetch):
    from services.import_batch_service import process_url_list
    urls = ["https://tavily.com/ok", "https://fail.example.com/bad", "https://exa.ai/ok2"]
    results = process_url_list(urls)
    assert len(results) == 3
    ok = [r for r in results if r.fetch_status == "success"]
    assert len(ok) >= 2


@patch("services.import_batch_service.fetch_url", side_effect=_mock_fetch)
def test_same_batch_duplicate_filtered(mock_fetch):
    from services.import_batch_service import process_url_list
    urls = [
        "https://tavily.com/post?utm_source=a",
        "https://tavily.com/post?utm_source=b",  # 同一正文 URL
        "https://exa.ai/unique",
    ]
    results = process_url_list(urls)
    # 同批次去重后只有 2 条被处理
    assert len(results) == 2


@patch("services.import_batch_service.fetch_url", side_effect=_mock_fetch)
def test_db_duplicate_marked(mock_fetch):
    import database
    from services.url_normalizer import normalize_url
    from services.import_batch_service import process_url_list

    # 先写入一条
    url = "https://exa.ai/existing"
    database.insert_record({
        "title": "existing", "source_url": url,
        "normalized_url": normalize_url(url),
    })

    results = process_url_list([url, "https://tavily.com/new"])
    dup = [r for r in results if r.is_duplicate]
    assert len(dup) == 1


@patch("services.import_batch_service.fetch_url", side_effect=_mock_fetch)
def test_status_counts_correct(mock_fetch):
    from services.import_batch_service import process_url_list, confirm_batch
    urls = [
        "https://tavily.com/ok1",
        "https://fail.example.com/bad",
        "https://restricted.example.com/locked",
    ]
    results = process_url_list(urls)
    selected = [i for i, r in enumerate(results) if not r.is_duplicate and not r.is_invalid_url]
    stats = confirm_batch(results, selected, import_mode="url_batch")

    assert stats["final_imported"] >= 1
    assert "batch_id" in stats


@patch("services.import_batch_service.fetch_url", side_effect=_mock_fetch)
def test_confirm_writes_to_db(mock_fetch):
    import database
    from services.import_batch_service import process_url_list, confirm_batch
    urls = ["https://tavily.com/write-test"]
    results = process_url_list(urls)
    confirm_batch(results, [0], import_mode="url_batch")

    records = database.get_records({"review_status": "待审核"})
    assert any("tavily.com/write-test" in (r.get("source_url") or "") for r in records)
