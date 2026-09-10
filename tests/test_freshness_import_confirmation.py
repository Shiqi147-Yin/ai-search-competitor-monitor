"""测试：新鲜度导入确认"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
from datetime import datetime, timezone
from services.freshness_filter import check_freshness


@pytest.fixture(autouse=True)
def isolated_db(tmp_path, monkeypatch):
    import config, database
    tmp_db = tmp_path / "freshness_import.db"
    monkeypatch.setattr(config, "DB_PATH", tmp_db)
    monkeypatch.setattr(database, "DB_PATH", tmp_db)
    database.init_db()
    database.migrate_db()
    yield


def _ref():
    return datetime(2026, 7, 21, 12, 0, 0, tzinfo=timezone.utc)


def test_within_window_imports_normally():
    """within_window 正常进入待审核区。"""
    import database
    from services.data_service import batch_insert
    rec = {
        "source_url": "https://tavily.com/new", "title": "New result",
        "normalized_url": "https://tavily.com/new",
        "review_status": "待审核",
        "freshness_status": "within_window",
    }
    stat = batch_insert([rec])
    assert stat["success"] == 1
    records = database.get_records({"review_status": "待审核"})
    assert len(records) == 1


def test_outside_window_still_pending_after_import():
    """超期结果导入后 review_status 仍为待审核，不进入主页。"""
    import database
    from services.data_service import batch_insert, get_weekly_dashboard
    rec = {
        "source_url": "https://tavily.com/old-2025", "title": "Old result",
        "normalized_url": "https://tavily.com/old-2025",
        "review_status": "待审核",
        "freshness_status": "outside_window",
    }
    batch_insert([rec])
    dashboard = get_weekly_dashboard()
    assert len(dashboard) == 0  # 不进入主页


def test_missing_date_gets_pending_flag():
    """日期缺失记录导入后标记待审核。"""
    import database
    from services.data_service import batch_insert
    rec = {
        "source_url": "https://tavily.com/no-date", "title": "No date result",
        "normalized_url": "https://tavily.com/no-date",
        "review_status": "待审核",
        "freshness_status": "date_missing",
    }
    stat = batch_insert([rec])
    assert stat["success"] == 1
    records = database.get_records({"review_status": "待审核"})
    assert records[0]["review_status"] == "待审核"
