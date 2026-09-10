"""测试：数据库层"""
import sqlite3
import sys
from pathlib import Path
import tempfile
import os

# 使用临时数据库，不污染生产数据
import pytest


@pytest.fixture(autouse=True)
def patch_db_path(tmp_path, monkeypatch):
    """将 DB_PATH 重定向到临时目录。"""
    import config
    tmp_db = tmp_path / "test.db"
    monkeypatch.setattr(config, "DB_PATH", tmp_db)
    import database
    monkeypatch.setattr(database, "DB_PATH", tmp_db)
    yield
    # 清理
    import importlib
    importlib.reload(database)


def test_init_db_creates_table(tmp_path, monkeypatch):
    """首次运行应自动建表。"""
    import config, database
    tmp_db = tmp_path / "test_init.db"
    monkeypatch.setattr(config, "DB_PATH", tmp_db)
    monkeypatch.setattr(database, "DB_PATH", tmp_db)

    database.init_db()

    conn = sqlite3.connect(str(tmp_db))
    tables = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='competitor_updates'"
    ).fetchall()
    conn.close()
    assert len(tables) == 1, "competitor_updates 表应已创建"


def test_insert_and_query(tmp_path, monkeypatch):
    """插入一条记录后可以查询回来。"""
    import config, database
    tmp_db = tmp_path / "test_iq.db"
    monkeypatch.setattr(config, "DB_PATH", tmp_db)
    monkeypatch.setattr(database, "DB_PATH", tmp_db)
    database.init_db()

    record = {
        "title": "测试动态",
        "source_url": "https://example.com/test1",
        "competitor": "Tavily",
        "review_status": "待审核",
        "week_id": "2026-W30",
        "priority": "高",
    }
    status = database.insert_record(record)
    assert status == "success"

    results = database.get_records({"competitor": "Tavily"})
    assert len(results) == 1
    assert results[0]["title"] == "测试动态"


def test_update_record(tmp_path, monkeypatch):
    """更新字段后可以查询到新值。"""
    import config, database
    tmp_db = tmp_path / "test_upd.db"
    monkeypatch.setattr(config, "DB_PATH", tmp_db)
    monkeypatch.setattr(database, "DB_PATH", tmp_db)
    database.init_db()

    database.insert_record({
        "title": "更新测试",
        "source_url": "https://example.com/test_update",
        "review_status": "待审核",
    })
    results = database.get_records({"review_status": "待审核"})
    rec_id = results[0]["id"]

    ok = database.update_record(rec_id, {"review_status": "已确认"})
    assert ok is True

    updated = database.get_records({"review_status": "已确认"})
    assert len(updated) == 1
    assert updated[0]["review_status"] == "已确认"


def test_duplicate_url_skipped(tmp_path, monkeypatch):
    """相同 source_url 第二次插入应返回 'duplicate' 而不是抛异常。"""
    import config, database
    tmp_db = tmp_path / "test_dup.db"
    monkeypatch.setattr(config, "DB_PATH", tmp_db)
    monkeypatch.setattr(database, "DB_PATH", tmp_db)
    database.init_db()

    rec = {"title": "重复测试", "source_url": "https://example.com/dup"}
    first = database.insert_record(rec)
    second = database.insert_record(rec)

    assert first == "success"
    assert second == "duplicate"

    all_records = database.get_records()
    assert len(all_records) == 1
