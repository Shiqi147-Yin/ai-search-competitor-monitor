"""test_official_monitor_history.py
验证 monitor_run_store：save/update/get/get_by_id。
"""
import sqlite3
import pytest
import database
from services.monitor_run_store import save_run, update_run, get_runs, get_run_by_id


@pytest.fixture
def tmp_db(tmp_path):
    db_file = str(tmp_path / "test_runs.db")
    conn = sqlite3.connect(db_file)
    conn.execute(database._CREATE_MONITOR_RUNS_SQL)
    conn.commit()
    conn.close()
    return db_file


def _base_run(**kw):
    run = {
        "competitor": "Tavily",
        "window_start": "2026-07-08",
        "window_end": "2026-07-17",
        "source_types": "all",
        "status": "completed",
        "blog_count": 1,
        "docs_count": 2,
        "github_count": 1,
        "total_valid": 4,
        "started_at": "2026-08-10T03:00:00Z",
    }
    run.update(kw)
    return run


def test_save_run_returns_id(tmp_db):
    run_id = save_run(_base_run(), db_path=tmp_db)
    assert isinstance(run_id, int)
    assert run_id > 0


def test_get_run_by_id(tmp_db):
    run_id = save_run(_base_run(blog_count=3), db_path=tmp_db)
    row = get_run_by_id(run_id, db_path=tmp_db)
    assert row is not None
    assert row["competitor"] == "Tavily"
    assert row["blog_count"] == 3


def test_get_run_by_id_not_found(tmp_db):
    result = get_run_by_id(9999, db_path=tmp_db)
    assert result is None


def test_update_run_status(tmp_db):
    run_id = save_run(_base_run(status="running"), db_path=tmp_db)
    update_run(run_id, {"status": "completed", "completed_at": "2026-08-10T03:10:00Z"}, db_path=tmp_db)
    row = get_run_by_id(run_id, db_path=tmp_db)
    assert row["status"] == "completed"
    assert row["completed_at"] == "2026-08-10T03:10:00Z"


def test_get_runs_returns_list(tmp_db):
    save_run(_base_run(blog_count=1), db_path=tmp_db)
    save_run(_base_run(blog_count=2, started_at="2026-08-11T03:00:00Z"), db_path=tmp_db)
    runs = get_runs(db_path=tmp_db)
    assert len(runs) == 2


def test_get_runs_filter_competitor(tmp_db):
    save_run(_base_run(competitor="Tavily"), db_path=tmp_db)
    save_run(_base_run(competitor="Exa"), db_path=tmp_db)
    tavily_runs = get_runs(competitor="Tavily", db_path=tmp_db)
    assert all(r["competitor"] == "Tavily" for r in tavily_runs)
    assert len(tavily_runs) == 1


def test_get_runs_order_newest_first(tmp_db):
    save_run(_base_run(started_at="2026-07-01T00:00:00Z"), db_path=tmp_db)
    save_run(_base_run(started_at="2026-08-01T00:00:00Z"), db_path=tmp_db)
    runs = get_runs(db_path=tmp_db)
    assert runs[0]["started_at"] > runs[1]["started_at"]


def test_update_run_ignores_unknown_columns(tmp_db):
    run_id = save_run(_base_run(), db_path=tmp_db)
    # 不应抛异常
    update_run(run_id, {"nonexistent_col": "value"}, db_path=tmp_db)
    row = get_run_by_id(run_id, db_path=tmp_db)
    assert row is not None
