"""测试：重新分析保留人工字段"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest


@pytest.fixture(autouse=True)
def isolated_db(tmp_path, monkeypatch):
    import config, database
    tmp_db = tmp_path / "reanalyze_test.db"
    monkeypatch.setattr(config, "DB_PATH", tmp_db)
    monkeypatch.setattr(database, "DB_PATH", tmp_db)
    database.init_db()
    database.migrate_db()
    yield


def _insert(url, title="Test", category="市场与运营", business_value="人工写的业务意义",
            auto_category="产品与功能"):
    import database
    from services.url_normalizer import normalize_url
    from datetime import datetime, timezone
    now = datetime.now(timezone.utc).isoformat()
    database.insert_record({
        "source_url": url, "normalized_url": normalize_url(url),
        "title": title, "competitor": "Exa", "source_platform": "X",
        "review_status": "待审核",
        "category": category, "business_value": business_value,
        "auto_category": auto_category,
        "collected_at": now, "updated_at": now,
    })
    with database._get_conn() as conn:
        row = conn.execute("SELECT id FROM competitor_updates WHERE source_url=?", (url,)).fetchone()
    return row[0]


def test_reanalyze_updates_auto_fields():
    """重新分析更新 auto_* 字段。"""
    import database
    from services.content_analyzer import analyze_record

    rid = _insert("https://exa.ai/reanalyze-a",
                  title="Exa Agent Skills launch")
    rec = database.get_records()[0]
    fresh = analyze_record(rec)
    database.update_record(rid, fresh.to_db_fields())

    updated = database.get_records()[0]
    assert updated.get("analysis_status") in ("analyzed", "partial")
    assert updated.get("auto_category") is not None


def test_reanalyze_does_not_overwrite_human_category():
    """重新分析不覆盖已保存的人工 category。"""
    import database
    from services.content_analyzer import analyze_record

    rid = _insert("https://exa.ai/reanalyze-b",
                  category="市场与运营",  # 人工值
                  auto_category="待评估")
    rec = database.get_records()[0]
    fresh = analyze_record(rec)
    # to_db_fields 只写 auto_* 字段
    database.update_record(rid, fresh.to_db_fields())

    updated = database.get_records()[0]
    assert updated["category"] == "市场与运营"  # 人工值保留


def test_reanalyze_does_not_overwrite_human_business_value():
    """重新分析不覆盖人工 business_value。"""
    import database
    from services.content_analyzer import analyze_record

    rid = _insert("https://exa.ai/reanalyze-c",
                  business_value="人工写的业务意义")
    rec = database.get_records()[0]
    fresh = analyze_record(rec)
    database.update_record(rid, fresh.to_db_fields())

    updated = database.get_records()[0]
    assert updated["business_value"] == "人工写的业务意义"


def test_empty_human_field_gets_new_suggestion_after_reanalyze():
    """人工字段为空时，重新分析后页面应能显示新建议（auto_* 有值）。"""
    import database
    from services.content_analyzer import analyze_record, form_default

    rid = _insert("https://exa.ai/reanalyze-d",
                  category="待评估",  # 默认值
                  business_value="",   # 空
                  title="Exa Cerebras integration for fast inference")
    rec = database.get_records()[0]
    fresh = analyze_record(rec)
    database.update_record(rid, fresh.to_db_fields())

    updated = database.get_records()[0]
    # form_default 应返回 auto_business_value（因为人工字段为空）
    val = form_default(updated, "business_value", "auto_business_value")
    assert val != ""  # 有自动建议可以展示
