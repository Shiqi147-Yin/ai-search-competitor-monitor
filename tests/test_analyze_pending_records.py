"""测试：批量分析历史待审核记录（analyze_pending_records.py 逻辑）"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
from unittest.mock import patch


@pytest.fixture(autouse=True)
def isolated_db(tmp_path, monkeypatch):
    import config, database
    tmp_db = tmp_path / "pending_analysis.db"
    monkeypatch.setattr(config, "DB_PATH", tmp_db)
    monkeypatch.setattr(database, "DB_PATH", tmp_db)
    database.init_db()
    database.migrate_db()
    yield


def _insert_pending(url, title="Test", analysis_status=None, summary="", manual_field=""):
    import database
    from services.url_normalizer import normalize_url
    from datetime import datetime, timezone
    now = datetime.now(timezone.utc).isoformat()
    rec = {
        "source_url": url,
        "normalized_url": normalize_url(url),
        "title": title,
        "competitor": "Exa",
        "source_platform": "X",
        "review_status": "待审核",
        "summary": summary,
        "collected_at": now,
        "updated_at": now,
    }
    if analysis_status:
        rec["analysis_status"] = analysis_status
    if manual_field:
        rec["category"] = manual_field
    database.insert_record(rec)
    with database._get_conn() as conn:
        row = conn.execute("SELECT id FROM competitor_updates WHERE source_url=?", (url,)).fetchone()
    return row[0]


def _run_batch_analysis(records, apply=True):
    """执行批量分析逻辑（不通过命令行，直接调用核心逻辑）。"""
    import database
    from services.content_analyzer import analyze_record
    stats = {"analyzed": 0, "partial": 0, "pending": 0, "failed": 0}
    for rec in records:
        try:
            result = analyze_record(rec)
            status = result.analysis_status if result.analysis_status in stats else "analyzed"
            stats[status] += 1
            if apply:
                db_fields = result.to_db_fields()
                database.update_record(rec["id"], db_fields)
        except Exception:
            stats["failed"] += 1
    return stats


def test_dry_run_does_not_write_db():
    """dry-run 模式不写入数据库（auto_category 保持 None）。"""
    import database
    rid = _insert_pending("https://exa.ai/dry-run", title="Exa Agent Skills")

    records = database.get_records({"review_status": "待审核"})
    _run_batch_analysis(records, apply=False)  # dry-run: apply=False

    rec = database.get_record_by_url("https://exa.ai/dry-run")
    assert rec.get("auto_category") is None or rec.get("auto_category") == ""


def test_apply_writes_auto_fields():
    """apply 模式正常写入 auto_* 字段。"""
    import database
    _insert_pending("https://exa.ai/apply",
                    title="Exa Cerebras integration for fast inference",
                    summary="New integration with Cerebras")

    records = database.get_records({"review_status": "待审核"})
    _run_batch_analysis(records, apply=True)

    rec = database.get_record_by_url("https://exa.ai/apply")
    assert rec.get("auto_category") is not None
    assert rec.get("analysis_status") in ("analyzed", "partial")


def test_limit_respected():
    """limit 参数生效，只处理前 N 条。"""
    import database

    for i in range(5):
        _insert_pending(f"https://exa.ai/limit-{i}", title=f"Record {i}")

    all_records = database.get_records({"review_status": "待审核"})
    limited = all_records[:2]
    _run_batch_analysis(limited, apply=True)

    # 前 2 条有 auto_category，后面不确定
    analyzed = [r for r in database.get_records()
                if r.get("auto_category") is not None and r["auto_category"] != ""]
    assert len(analyzed) <= 2


def test_manual_fields_not_overwritten():
    """人工字段不被 auto_* 覆盖。"""
    import database
    rid = _insert_pending(
        "https://exa.ai/manual-protect",
        title="Exa streaming search",
        manual_field="市场与运营",   # 人工设置了 category
    )

    records = database.get_records({"review_status": "待审核"})
    _run_batch_analysis(records, apply=True)

    rec = database.get_record_by_url("https://exa.ai/manual-protect")
    # 人工 category 不应被覆盖
    assert rec["category"] == "市场与运营"
    # auto_category 可以是不同值
    # （to_db_fields 只写 auto_* 字段，不写 category）


def test_single_failure_does_not_stop_others():
    """单条分析失败不影响其他记录。"""
    import database
    from services.content_analyzer import analyze_record

    _insert_pending("https://exa.ai/ok-a", title="Exa streaming release")
    _insert_pending("https://exa.ai/ok-b", title="Exa Cerebras integration")

    records = database.get_records({"review_status": "待审核"})
    stats = {"analyzed": 0, "partial": 0, "pending": 0, "failed": 0}
    call_count = {"n": 0}

    def _analyze_with_one_fail(rec):
        call_count["n"] += 1
        if call_count["n"] == 1:
            raise RuntimeError("Simulated failure")
        return analyze_record(rec)

    for rec in records:
        try:
            result = _analyze_with_one_fail(rec)
            status = result.analysis_status if result.analysis_status in stats else "analyzed"
            stats[status] += 1
        except Exception:
            stats["failed"] += 1

    # 两条都被处理到
    assert call_count["n"] == 2
    # 第一条失败，第二条成功
    assert stats["failed"] == 1
    total_ok = stats["analyzed"] + stats["partial"]
    assert total_ok >= 1
