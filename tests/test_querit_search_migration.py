"""测试：Querit 检索数据库 Migration"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import sqlite3
import pytest


@pytest.fixture
def fresh_db(tmp_path, monkeypatch):
    import config, database
    tmp_db = tmp_path / "search_migration_test.db"
    monkeypatch.setattr(config, "DB_PATH", tmp_db)
    monkeypatch.setattr(database, "DB_PATH", tmp_db)
    return database, tmp_db


def _get_tables(tmp_db):
    with sqlite3.connect(str(tmp_db)) as conn:
        rows = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()
    return {r[0] for r in rows}


def test_new_tables_created(fresh_db):
    """migration 后三张新表都存在。"""
    database, tmp_db = fresh_db
    database.init_db()
    database.migrate_db()
    tables = _get_tables(tmp_db)
    assert "querit_search_runs" in tables
    assert "querit_search_queries" in tables
    assert "querit_search_results" in tables


def test_migration_idempotent(fresh_db):
    """多次 migration 不报错。"""
    database, _ = fresh_db
    database.init_db()
    database.migrate_db()
    database.migrate_db()
    database.migrate_db()


def test_existing_data_preserved(fresh_db):
    """migration 不丢失已有 competitor_updates 记录。"""
    database, _ = fresh_db
    database.init_db()
    database.insert_record({"title": "old record", "source_url": "https://example.com/old"})
    count_before = len(database.get_records())
    database.migrate_db()
    assert len(database.get_records()) == count_before


def test_no_api_key_in_tables(fresh_db):
    """检索相关表不包含 API Key 相关字段。"""
    database, tmp_db = fresh_db
    database.init_db()
    database.migrate_db()
    with sqlite3.connect(str(tmp_db)) as conn:
        for table in ("querit_search_runs", "querit_search_queries", "querit_search_results"):
            cols = {r[1] for r in conn.execute(f"PRAGMA table_info({table})").fetchall()}
            for bad in ("api_key", "authorization", "token", "secret"):
                assert bad not in cols, f"表 {table} 包含敏感字段 {bad}"


def test_create_and_query_search_run(fresh_db):
    """可以创建并查询检索运行记录。"""
    database, _ = fresh_db
    database.init_db()
    database.migrate_db()
    run_id = database.create_search_run({
        "started_at": "2026-07-20T00:00:00Z",
        "status": "completed",
        "competitor_scope": "Tavily",
        "created_at": "2026-07-20T00:00:00Z",
    })
    assert run_id > 0
    runs = database.get_search_runs()
    assert len(runs) == 1
    assert runs[0]["competitor_scope"] == "Tavily"
