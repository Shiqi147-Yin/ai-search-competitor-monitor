"""测试：接受全部建议按钮行为"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest


@pytest.fixture(autouse=True)
def isolated_db(tmp_path, monkeypatch):
    import config, database
    tmp_db = tmp_path / "accept_test.db"
    monkeypatch.setattr(config, "DB_PATH", tmp_db)
    monkeypatch.setattr(database, "DB_PATH", tmp_db)
    database.init_db()
    database.migrate_db()
    yield


def _insert(url, category="待评估", auto_category="产品与功能",
            auto_priority="高", auto_business_value="系统建议业务意义",
            auto_suggested_action="系统建议动作"):
    import database
    from services.url_normalizer import normalize_url
    from datetime import datetime, timezone
    now = datetime.now(timezone.utc).isoformat()
    database.insert_record({
        "source_url": url, "normalized_url": normalize_url(url),
        "title": "Test", "competitor": "Exa", "source_platform": "X",
        "review_status": "待审核", "category": category,
        "auto_category": auto_category, "auto_priority": auto_priority,
        "auto_business_value": auto_business_value,
        "auto_suggested_action": auto_suggested_action,
        "collected_at": now, "updated_at": now,
    })
    with database._get_conn() as conn:
        row = conn.execute("SELECT id FROM competitor_updates WHERE source_url=?", (url,)).fetchone()
    return row[0]


def test_accept_suggestion_writes_to_human_fields():
    """接受建议后，auto_* 值被写入人工字段。"""
    import database
    rid = _insert("https://exa.ai/accept-test")

    # 模拟"接受全部建议"逻辑
    rec = database.get_records()[0]
    auto_fields = {
        "category":         rec.get("auto_category") or "待评估",
        "business_value":   rec.get("auto_business_value") or "",
        "priority":         rec.get("auto_priority") or "中",
        "suggested_action": rec.get("auto_suggested_action") or "",
    }
    database.update_record(rid, auto_fields)

    updated = database.get_records()[0]
    assert updated["category"] == "产品与功能"
    assert updated["business_value"] == "系统建议业务意义"


def test_accept_suggestion_does_not_confirm_record():
    """接受建议不改变 review_status 为已确认。"""
    import database
    rid = _insert("https://exa.ai/no-confirm")

    rec = database.get_records()[0]
    auto_fields = {"category": rec.get("auto_category") or "待评估"}
    database.update_record(rid, auto_fields)

    updated = database.get_records()[0]
    assert updated["review_status"] == "待审核"


def test_accept_does_not_overwrite_existing_human_modification():
    """已有人工修改的字段，不应被接受建议覆盖（除非用户主动确认）。"""
    import database
    rid = _insert("https://exa.ai/human-first",
                  category="市场与运营",  # 人工已修改
                  auto_category="产品与功能")

    rec = database.get_records()[0]
    # 只接受 auto_* 中的非人工修改字段（模拟按钮行为不覆盖已修改字段）
    # 人工 category=市场与运营 ≠ 默认值，不覆盖
    from services.content_analyzer import _is_empty_or_default
    auto_fields = {}
    for k, auto_k in [("category", "auto_category"), ("business_value", "auto_business_value")]:
        if _is_empty_or_default(k, rec.get(k)):
            auto_fields[k] = rec.get(auto_k) or ""
    if auto_fields:
        database.update_record(rid, auto_fields)

    updated = database.get_records()[0]
    # 人工 category 不被覆盖
    assert updated["category"] == "市场与运营"
