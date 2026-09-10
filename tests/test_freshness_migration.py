"""测试：新鲜度 migration"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import sqlite3
import pytest


@pytest.fixture
def fresh_db(tmp_path, monkeypatch):
    import config, database
    tmp_db = tmp_path / "freshness_migration.db"
    monkeypatch.setattr(config, "DB_PATH", tmp_db)
    monkeypatch.setattr(database, "DB_PATH", tmp_db)
    return database, tmp_db


def test_freshness_fields_in_search_results(fresh_db):
    """querit_search_results 含新鲜度字段。"""
    database, tmp_db = fresh_db
    database.init_db()
    database.migrate_db()
    with sqlite3.connect(str(tmp_db)) as conn:
        cols = {r[1] for r in conn.execute("PRAGMA table_info(querit_search_results)").fetchall()}
    for field in ("freshness_status", "days_from_search", "date_status",
                  "normalized_published_at", "window_start", "window_end"):
        assert field in cols, f"缺少字段 {field}"


def test_search_runs_has_freshness_counts(fresh_db):
    """querit_search_runs 含新鲜度统计字段。"""
    database, tmp_db = fresh_db
    database.init_db()
    database.migrate_db()
    with sqlite3.connect(str(tmp_db)) as conn:
        cols = {r[1] for r in conn.execute("PRAGMA table_info(querit_search_runs)").fetchall()}
    for field in ("within_window_count", "outside_window_count",
                  "missing_date_count", "window_start", "window_end"):
        assert field in cols, f"querit_search_runs 缺少字段 {field}"


def test_migration_idempotent(fresh_db):
    database, _ = fresh_db
    database.init_db()
    database.migrate_db()
    database.migrate_db()  # 不报错


def test_old_data_preserved(fresh_db):
    database, _ = fresh_db
    database.init_db()
    database.insert_record({"title": "old", "source_url": "https://example.com/old"})
    count = len(database.get_records())
    database.migrate_db()
    assert len(database.get_records()) == count
