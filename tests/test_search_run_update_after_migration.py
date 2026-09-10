"""测试：migration 后可更新 within_window_count 等字段"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest


@pytest.fixture(autouse=True)
def isolated_db(tmp_path, monkeypatch):
    import config, database
    tmp_db = tmp_path / "run_update_test.db"
    monkeypatch.setattr(config, "DB_PATH", tmp_db)
    monkeypatch.setattr(database, "DB_PATH", tmp_db)
    database.init_db()
    database.run_migrations()
    yield


def test_can_update_within_window_count():
    import database
    from datetime import datetime, timezone
    now = datetime.now(timezone.utc).isoformat()
    run_id = database.create_search_run({
        "started_at": now, "status": "running", "created_at": now,
    })
    # 这行在修复前会抛 sqlite3.OperationalError: no such column
    database.update_search_run(run_id, {
        "within_window_count": 5,
        "outside_window_count": 3,
        "missing_date_count": 2,
        "invalid_date_count": 0,
        "future_date_count": 0,
        "status": "completed",
    })
    runs = database.get_search_runs()
    assert runs[0]["within_window_count"] == 5
    assert runs[0]["outside_window_count"] == 3


def test_can_update_window_start_end():
    import database
    from datetime import datetime, timezone
    now = datetime.now(timezone.utc).isoformat()
    run_id = database.create_search_run({"started_at": now, "status": "r", "created_at": now})
    database.update_search_run(run_id, {
        "window_start": "2026-07-14T00:00:00Z",
        "window_end": "2026-07-21T00:00:00Z",
    })
    runs = database.get_search_runs()
    assert runs[0]["window_start"] == "2026-07-14T00:00:00Z"


def test_no_operational_error_on_freshness_update():
    """不再抛 OperationalError: no such column。"""
    import database
    from datetime import datetime, timezone
    now = datetime.now(timezone.utc).isoformat()
    run_id = database.create_search_run({"started_at": now, "status": "r", "created_at": now})
    try:
        database.update_search_run(run_id, {
            "within_window_count": 1,
            "status": "completed",
        })
        ok = True
    except Exception:
        ok = False
    assert ok
