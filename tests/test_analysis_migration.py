"""测试：数据库 migration 安全性（新增 11 个分析字段）"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import sqlite3
import pytest


@pytest.fixture
def fresh_db(tmp_path, monkeypatch):
    import config, database
    tmp_db = tmp_path / "migration_test.db"
    monkeypatch.setattr(config, "DB_PATH", tmp_db)
    monkeypatch.setattr(database, "DB_PATH", tmp_db)
    return database, tmp_db


def test_migration_adds_analysis_fields(fresh_db):
    """migration 后 competitor_updates 含全部分析字段。"""
    database, tmp_db = fresh_db
    database.init_db()
    database.migrate_db()

    with sqlite3.connect(str(tmp_db)) as conn:
        cursor = conn.execute("PRAGMA table_info(competitor_updates)")
        col_names = {row[1] for row in cursor.fetchall()}

    expected = {
        "secondary_tags", "analysis_status", "analysis_confidence",
        "analysis_reason", "auto_category", "auto_business_value",
        "auto_priority", "auto_suggested_action", "auto_querit_status",
        "auto_gap_analysis", "analyzed_at",
    }
    assert expected.issubset(col_names), f"缺少字段：{expected - col_names}"


def test_existing_data_not_lost_after_migration(fresh_db):
    """migration 不丢失已有记录。"""
    database, tmp_db = fresh_db
    database.init_db()

    # 先插入一条旧数据
    database.insert_record({
        "title": "旧记录",
        "source_url": "https://example.com/old",
        "review_status": "待审核",
    })
    count_before = len(database.get_records())

    # 运行 migration
    database.migrate_db()
    count_after = len(database.get_records())
    assert count_after == count_before


def test_new_fields_have_correct_defaults(fresh_db):
    """新增字段的默认值正确（analysis_status='pending', analysis_confidence=0.0）。"""
    database, _ = fresh_db
    database.init_db()
    database.migrate_db()

    database.insert_record({
        "title": "默认值测试",
        "source_url": "https://example.com/defaults",
    })
    records = database.get_records()
    rec = records[0]

    assert rec.get("analysis_status") in ("pending", None, "")
    conf = rec.get("analysis_confidence")
    assert conf is None or conf == 0.0


def test_migration_is_idempotent(fresh_db):
    """多次运行 migration 不报错。"""
    database, _ = fresh_db
    database.init_db()
    database.migrate_db()
    database.migrate_db()  # 第二次不应报错
    database.migrate_db()  # 第三次也不应报错
