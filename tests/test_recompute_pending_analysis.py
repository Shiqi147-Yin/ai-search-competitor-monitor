"""测试：--recompute 模式"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest


@pytest.fixture(autouse=True)
def isolated_db(tmp_path, monkeypatch):
    import config, database
    tmp_db = tmp_path / "recompute_test.db"
    monkeypatch.setattr(config, "DB_PATH", tmp_db)
    monkeypatch.setattr(database, "DB_PATH", tmp_db)
    database.init_db()
    database.migrate_db()
    yield


def _insert(url, title="Test", analysis_status="analyzed",
            analysis_confidence=1.0, category="市场与运营"):
    import database
    from services.url_normalizer import normalize_url
    from datetime import datetime, timezone
    now = datetime.now(timezone.utc).isoformat()
    database.insert_record({
        "source_url": url, "normalized_url": normalize_url(url),
        "title": title, "competitor": "Exa", "source_platform": "LinkedIn",
        "fetch_status": "restricted", "fetch_error": "HTTP 451",
        "review_status": "待审核",
        "analysis_status": analysis_status,
        "analysis_confidence": analysis_confidence,
        "category": category,
        "collected_at": now, "updated_at": now,
    })
    with database._get_conn() as conn:
        row = conn.execute("SELECT id FROM competitor_updates WHERE source_url=?", (url,)).fetchone()
    return row[0]


def _run_recompute(records, apply=True):
    import database
    from services.content_analyzer import analyze_record
    stats = {"analyzed": 0, "partial": 0, "pending": 0, "failed": 0}
    for rec in records:
        try:
            result = analyze_record(rec)
            status = result.analysis_status if result.analysis_status in stats else "analyzed"
            stats[status] += 1
            if apply:
                database.update_record(rec["id"], result.to_db_fields())
        except Exception:
            stats["failed"] += 1
    return stats


def test_recompute_dry_run_does_not_write():
    """--recompute --dry-run 不写数据库（置信度保持旧值）。"""
    import database
    rid = _insert("https://linkedin.com/posts/exa-summit",
                  analysis_confidence=1.0)

    records = database.get_records({"review_status": "待审核"})
    _run_recompute(records, apply=False)

    rec = database.get_record_by_url("https://linkedin.com/posts/exa-summit")
    # 未写入时，分析字段应仍为旧值（NULL 或 1.0）
    assert rec.get("analysis_confidence") in (None, 1.0, "")


def test_recompute_apply_updates_confidence():
    """--recompute --apply 更新 auto_* 和 confidence。"""
    import database
    rid = _insert("https://linkedin.com/posts/exa-raise",
                  analysis_confidence=1.0)

    records = database.get_records({"review_status": "待审核"})
    _run_recompute(records, apply=True)

    rec = database.get_record_by_url("https://linkedin.com/posts/exa-raise")
    new_conf = rec.get("analysis_confidence") or 0
    assert new_conf <= 0.40, f"重新计算后置信度 {new_conf} 仍超过 0.40"


def test_recompute_does_not_overwrite_human_category():
    """--recompute 不覆盖人工 category。"""
    import database
    rid = _insert("https://linkedin.com/posts/human-cat",
                  category="产品与功能")  # 人工设置

    records = database.get_records({"review_status": "待审核"})
    _run_recompute(records, apply=True)

    rec = database.get_record_by_url("https://linkedin.com/posts/human-cat")
    assert rec["category"] == "产品与功能"


def test_recompute_does_not_change_review_status():
    """--recompute 不改变 review_status。"""
    import database
    _insert("https://linkedin.com/posts/review-status")

    records = database.get_records({"review_status": "待审核"})
    _run_recompute(records, apply=True)

    rec = database.get_record_by_url("https://linkedin.com/posts/review-status")
    assert rec["review_status"] == "待审核"


def test_recompute_does_not_add_rows():
    """--recompute 不新增数据库行。"""
    import database
    _insert("https://linkedin.com/posts/no-new-row")
    count_before = len(database.get_records())

    records = database.get_records({"review_status": "待审核"})
    _run_recompute(records, apply=True)

    assert len(database.get_records()) == count_before
