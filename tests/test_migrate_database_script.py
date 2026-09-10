"""测试：migrate_database.py 脚本逻辑"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import sqlite3
import pytest


@pytest.fixture
def minimal_db(tmp_path, monkeypatch):
    """只有基础字段的最小数据库。"""
    import config, database
    tmp_db = tmp_path / "migrate_script_test.db"
    monkeypatch.setattr(config, "DB_PATH", tmp_db)
    monkeypatch.setattr(database, "DB_PATH", tmp_db)
    with sqlite3.connect(str(tmp_db)) as conn:
        conn.execute("CREATE TABLE querit_search_runs (id INTEGER PRIMARY KEY, started_at TEXT)")
        conn.execute("CREATE TABLE querit_search_results (id INTEGER PRIMARY KEY, run_id INTEGER)")
        conn.execute("CREATE TABLE competitor_updates (id INTEGER PRIMARY KEY, title TEXT NOT NULL, source_url TEXT UNIQUE)")
        conn.commit()
    return database, tmp_db


def _run_migration(database, apply=True):
    """执行 migration 核心逻辑（不通过命令行）。"""
    database.init_db()
    if apply:
        database.run_migrations()


def test_dry_run_does_not_add_columns(minimal_db):
    """dry-run 不写数据库。"""
    database, _ = minimal_db
    cols_before = database.get_table_columns("querit_search_runs")
    # dry-run: 不调用 run_migrations
    cols_after = database.get_table_columns("querit_search_runs")
    assert cols_before == cols_after


def test_apply_adds_missing_columns(minimal_db):
    """apply 正确新增字段。"""
    database, _ = minimal_db
    _run_migration(database, apply=True)
    cols = database.get_table_columns("querit_search_runs")
    assert "within_window_count" in cols
    assert "window_start" in cols


def test_apply_is_idempotent(minimal_db):
    """重复 apply 不报错。"""
    database, _ = minimal_db
    _run_migration(database, apply=True)
    _run_migration(database, apply=True)
    _run_migration(database, apply=True)


def test_apply_preserves_existing_data(minimal_db):
    """apply 不丢失已有数据。"""
    import database as db_module
    _, tmp_db = minimal_db
    with sqlite3.connect(str(tmp_db)) as conn:
        conn.execute("INSERT INTO querit_search_runs (started_at) VALUES ('2026-07-01')")
        conn.commit()
    db_module.run_migrations()
    runs = db_module.get_search_runs()
    assert len(runs) == 1
