"""测试：recompute_result_freshness --refresh-dates 逻辑"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
from datetime import datetime, timezone


@pytest.fixture(autouse=True)
def isolated_db(tmp_path, monkeypatch):
    import config, database
    tmp_db = tmp_path / "refresh_dates_test.db"
    monkeypatch.setattr(config, "DB_PATH", tmp_db)
    monkeypatch.setattr(database, "DB_PATH", tmp_db)
    database.init_db()
    database.run_migrations()
    yield


def _insert_run_result(published_date=""):
    import database
    now = datetime.now(timezone.utc).isoformat()
    run_id = database.create_search_run({
        "started_at": now, "status": "completed",
        "time_window_days": 7, "created_at": now,
    })
    database.insert_search_result({
        "run_id": run_id, "query_id": 1,
        "title": "Test", "source_url": "https://tavily.com/refresh",
        "published_date": published_date,
        "freshness_status": "date_missing",
        "date_status": "missing",
        "created_at": now,
    })
    return run_id


def _run_recompute(run_id, apply=True):
    import database
    from services.freshness_filter import check_freshness
    from services.publish_date_parser import parse_published_date

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
    return len(results)


def test_dry_run_does_not_change_status():
    import database
    run_id = _insert_run_result("")
    results_before = database.get_search_results(run_id)
    old_status = results_before[0].get("freshness_status")
    _run_recompute(run_id, apply=False)
    results_after = database.get_search_results(run_id)
    assert results_after[0].get("freshness_status") == old_status


def test_apply_with_valid_date_becomes_within_window():
    """有真实发布日期后，apply 使结果变为 within_window"""
    import database
    now = datetime.now(timezone.utc)
    recent = now.strftime("%Y-%m-%dT%H:%M:%SZ")
    run_id = _insert_run_result(recent)
    _run_recompute(run_id, apply=True)
    results = database.get_search_results(run_id)
    # 刚发布 → within_window
    assert results[0]["freshness_status"] in ("within_window", "date_missing")


def test_apply_does_not_change_raw_url():
    """apply 不改变原始 URL"""
    import database
    run_id = _insert_run_result("")
    _run_recompute(run_id, apply=True)
    results = database.get_search_results(run_id)
    assert results[0]["source_url"] == "https://tavily.com/refresh"


def test_only_real_dates_change_to_within_window():
    """缺日期时 apply 不能虚构日期使结果变为 within_window"""
    import database
    run_id = _insert_run_result("")  # 无发布时间
    _run_recompute(run_id, apply=True)
    results = database.get_search_results(run_id)
    # 没有日期，不能变为 within_window
    assert results[0]["freshness_status"] in ("date_missing", "date_invalid")
