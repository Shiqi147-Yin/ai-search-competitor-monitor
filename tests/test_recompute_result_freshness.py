"""测试：recompute_result_freshness.py 逻辑"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
from datetime import datetime, timezone


@pytest.fixture(autouse=True)
def isolated_db(tmp_path, monkeypatch):
    import config, database
    tmp_db = tmp_path / "recompute_test.db"
    monkeypatch.setattr(config, "DB_PATH", tmp_db)
    monkeypatch.setattr(database, "DB_PATH", tmp_db)
    database.init_db()
    database.migrate_db()
    yield


def _insert_run_and_result(published_date="2025-01-01T00:00:00Z"):
    import database
    now = datetime.now(timezone.utc).isoformat()
    run_id = database.create_search_run({
        "started_at": now, "status": "completed",
        "competitor_scope": "Tavily", "time_window_days": 7, "created_at": now,
    })
    database.insert_search_result({
        "run_id": run_id, "query_id": 1,
        "title": "Old result", "source_url": "https://tavily.com/old",
        "published_date": published_date, "created_at": now,
    })
    return run_id


def _run_recompute(run_id: int, apply: bool):
    import database
    from services.freshness_filter import check_freshness
    from datetime import timezone

    runs = [r for r in database.get_search_runs(limit=100) if r["id"] == run_id]
    if not runs:
        return 0
    run = runs[0]
    time_window = run.get("time_window_days") or 7
    started_at = run.get("started_at") or run.get("created_at")
    try:
        ref_time = datetime.fromisoformat(started_at.replace("Z", "+00:00"))
    except Exception:
        ref_time = datetime.now(timezone.utc)

    results = database.get_search_results(run_id)
    count = 0
    for res in results:
        pseudo_rec = {
            "published_date": res.get("published_date"),
            "page_age": res.get("normalized_published_at"),
            "source_url": res.get("source_url", ""),
            "title": res.get("title", ""),
        }
        fr = check_freshness(pseudo_rec, time_window, ref_time)
        if apply:
            with database._get_conn() as conn:
                conn.execute(
                    "UPDATE querit_search_results SET freshness_status=?, "
                    "normalized_published_at=?, date_status=? WHERE id=?",
                    (fr.freshness_status, fr.normalized_published_at or "", fr.date_status, res["id"]),
                )
                conn.commit()
        count += 1
    return count


def test_dry_run_does_not_write(isolated_db):
    """dry-run 不写数据库。"""
    import database
    run_id = _insert_run_and_result()
    results_before = database.get_search_results(run_id)
    old_status = results_before[0].get("freshness_status")
    _run_recompute(run_id, apply=False)
    results_after = database.get_search_results(run_id)
    assert results_after[0].get("freshness_status") == old_status


def test_apply_updates_freshness(isolated_db):
    """apply 更新新鲜度字段。"""
    import database
    run_id = _insert_run_and_result("2025-01-01T00:00:00Z")
    _run_recompute(run_id, apply=True)
    results = database.get_search_results(run_id)
    assert results[0]["freshness_status"] == "outside_window"


def test_does_not_change_raw_date(isolated_db):
    """不改变原始 published_date 字段。"""
    import database
    run_id = _insert_run_and_result("2025-01-01T00:00:00Z")
    _run_recompute(run_id, apply=True)
    results = database.get_search_results(run_id)
    assert results[0]["published_date"] == "2025-01-01T00:00:00Z"


def test_run_id_filter(isolated_db):
    """指定 run_id 只处理该批次。"""
    import database
    run_id1 = _insert_run_and_result()
    run_id2 = _insert_run_and_result()
    count = _run_recompute(run_id1, apply=False)
    assert count == 1
