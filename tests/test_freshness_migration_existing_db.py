"""测试：对旧结构数据库执行 migration 后新字段存在"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import sqlite3
import pytest


@pytest.fixture
def old_db(tmp_path, monkeypatch):
    """创建只有基础表（无新鲜度字段）的旧结构数据库。"""
    import config, database
    tmp_db = tmp_path / "old_struct.db"
    monkeypatch.setattr(config, "DB_PATH", tmp_db)
    monkeypatch.setattr(database, "DB_PATH", tmp_db)
    # 只建基础表，模拟旧数据库
    with sqlite3.connect(str(tmp_db)) as conn:
        conn.execute("""
            CREATE TABLE querit_search_runs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                started_at TEXT, status TEXT, competitor_scope TEXT,
                created_at TEXT
            )""")
        conn.execute("""
            CREATE TABLE querit_search_results (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                run_id INTEGER, title TEXT, source_url TEXT, created_at TEXT
            )""")
        conn.execute("""
            CREATE TABLE competitor_updates (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL, source_url TEXT UNIQUE
            )""")
        conn.commit()
    return database, tmp_db


def test_migration_adds_freshness_fields_to_runs(old_db):
    database, _ = old_db
    database.run_migrations()
    cols = database.get_table_columns("querit_search_runs")
    for field in ("within_window_count", "outside_window_count",
                  "missing_date_count", "window_start", "window_end"):
        assert field in cols, f"querit_search_runs 缺少 {field}"


def test_migration_adds_freshness_fields_to_results(old_db):
    database, _ = old_db
    database.run_migrations()
    cols = database.get_table_columns("querit_search_results")
    for field in ("freshness_status", "date_status", "normalized_published_at",
                  "days_from_search", "window_start"):
        assert field in cols, f"querit_search_results 缺少 {field}"


def test_old_data_preserved(old_db):
    database, tmp_db = old_db
    with sqlite3.connect(str(tmp_db)) as conn:
        conn.execute("INSERT INTO querit_search_runs (started_at, status, created_at) VALUES ('2026-07-01', 'completed', '2026-07-01')")
        conn.commit()
    database.run_migrations()
    runs = database.get_search_runs()
    assert len(runs) == 1


def test_migration_idempotent(old_db):
    database, _ = old_db
    database.run_migrations()
    database.run_migrations()
    database.run_migrations()  # 不报错
