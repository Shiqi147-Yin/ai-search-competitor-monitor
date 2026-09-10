"""测试：Querit 日期完整管道（从 SearchResult → adapter → freshness）"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
from datetime import datetime, timezone
from services.querit_client import SearchResult
from services.freshness_filter import check_freshness


@pytest.fixture(autouse=True)
def isolated_db(tmp_path, monkeypatch):
    import config, database
    tmp_db = tmp_path / "date_pipeline.db"
    monkeypatch.setattr(config, "DB_PATH", tmp_db)
    monkeypatch.setattr(database, "DB_PATH", tmp_db)
    database.init_db()
    database.run_migrations()
    yield


def _make_sr(pub_date="2026-07-18T10:00:00Z", url="https://tavily.com/test"):
    return SearchResult(
        title="Test", url=url,
        content="content", summary="summary",
        published_date=pub_date,
        rank=1, query="test", raw_source="", raw_metadata={},
    )


def test_adapter_puts_published_date_in_rec():
    """adapt_result 将 SearchResult.published_date 写入 rec['published_date']（两个 d）"""
    from services.querit_result_adapter import adapt_result
    sr = _make_sr()
    rec = adapt_result(sr, "run1", 1)
    assert "published_date" in rec
    assert rec["published_date"] == "2026-07-18T10:00:00Z"


def test_freshness_uses_published_date():
    """freshness_filter 能从 rec['published_date'] 读取并判断窗口"""
    from services.querit_result_adapter import adapt_result
    sr = _make_sr(pub_date="2026-07-18T10:00:00Z")
    rec = adapt_result(sr, "run1", 1)
    ref = datetime(2026, 7, 21, 0, 0, 0, tzinfo=timezone.utc)
    fr = check_freshness(rec, 7, ref)
    assert fr.freshness_status == "within_window", (
        f"期望 within_window，实际 {fr.freshness_status}，reason: {fr.freshness_reason}"
    )


def test_old_2025_result_is_outside_window():
    """2025 年结果判定为 outside_window"""
    from services.querit_result_adapter import adapt_result
    sr = _make_sr(pub_date="2025-01-01T00:00:00Z")
    rec = adapt_result(sr, "run1", 1)
    ref = datetime(2026, 7, 21, 0, 0, 0, tzinfo=timezone.utc)
    fr = check_freshness(rec, 7, ref)
    assert fr.freshness_status == "outside_window"


def test_no_date_is_date_missing():
    """没有 published_date 时 freshness=date_missing"""
    from services.querit_result_adapter import adapt_result
    sr = _make_sr(pub_date="")
    rec = adapt_result(sr, "run1", 1)
    ref = datetime(2026, 7, 21, 0, 0, 0, tzinfo=timezone.utc)
    fr = check_freshness(rec, 7, ref)
    assert fr.freshness_status == "date_missing"


def test_database_insert_preserves_date(tmp_path, monkeypatch):
    """数据库写入后可查回 published_date"""
    import database, config
    tmp_db = tmp_path / "date_db_test.db"
    monkeypatch.setattr(config, "DB_PATH", tmp_db)
    monkeypatch.setattr(database, "DB_PATH", tmp_db)
    database.init_db()
    database.run_migrations()

    from services.querit_result_adapter import adapt_result
    from datetime import timezone
    sr = _make_sr(pub_date="2026-07-18T10:00:00Z", url="https://tavily.com/unique-db")
    rec = adapt_result(sr, "run99", 1)

    run_id = database.create_search_run({
        "started_at": datetime.now(timezone.utc).isoformat(),
        "status": "running",
        "created_at": datetime.now(timezone.utc).isoformat(),
    })
    database.insert_search_result({
        "run_id": run_id, "query_id": 1,
        "title": rec.get("title"),
        "source_url": rec.get("source_url"),
        "published_date": rec.get("published_date"),
        "created_at": datetime.now(timezone.utc).isoformat(),
    })

    results = database.get_search_results(run_id)
    assert len(results) == 1
    assert results[0]["published_date"] == "2026-07-18T10:00:00Z"
