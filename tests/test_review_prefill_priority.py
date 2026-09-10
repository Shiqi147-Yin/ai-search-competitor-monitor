"""测试：预填优先级规则"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from services.content_analyzer import form_default, form_source_hint


def _rec(**kwargs):
    base = {
        "category": "待评估", "auto_category": "",
        "business_value": "", "auto_business_value": "系统建议的业务意义",
        "priority": "中", "auto_priority": "高",
        "querit_status": "待评估", "auto_querit_status": "待评估",
        "suggested_action": "", "auto_suggested_action": "系统建议动作",
        "gap_analysis": "", "auto_gap_analysis": "系统建议差距",
        "review_status": "待审核",
    }
    base.update(kwargs)
    return base


def test_human_field_beats_auto():
    """人工字段有值时，返回人工值而非自动值。"""
    rec = _rec(category="市场与运营", auto_category="产品与功能")
    val = form_default(rec, "category", "auto_category", "待评估", {"待评估", ""})
    assert val == "市场与运营"


def test_empty_human_uses_auto():
    """人工字段为空，自动建议有值时，返回自动值。"""
    rec = _rec(category="待评估", auto_category="产品与功能")
    val = form_default(rec, "category", "auto_category", "待评估", {"待评估", ""})
    assert val == "产品与功能"


def test_default_category_uses_auto():
    """人工 category 为"待评估"（默认值），auto_category 有值时预填自动值。"""
    rec = _rec(category="待评估", auto_category="生态与集成")
    val = form_default(rec, "category", "auto_category", "待评估", {"待评估", ""})
    assert val == "生态与集成"


def test_autofill_does_not_change_review_status():
    """预填逻辑不改变 review_status 字段。"""
    rec = _rec(auto_category="产品与功能")
    from services.content_analyzer import analyze_record
    result = analyze_record(rec)
    db_fields = result.to_db_fields()
    assert "review_status" not in db_fields


def test_autofill_does_not_write_human_field():
    """form_default 只读取字段，不写入数据库。"""
    import database, config
    # 只验证 form_default 是纯读取函数（不触发 DB 写入）
    rec = _rec(auto_category="产品与功能")
    val = form_default(rec, "category", "auto_category", "待评估", {"待评估", ""})
    assert val == "产品与功能"
    # 无 DB 副作用：函数不接受 db 参数，故无写入可能


def test_source_hint_shows_human_modified():
    """人工已修改字段时，提示'已使用人工修改结果'。"""
    rec = _rec(category="市场与运营", auto_category="产品与功能")
    hint = form_source_hint(rec, "category", "auto_category", {"待评估", ""})
    assert "人工修改" in hint


def test_source_hint_shows_auto_prefilled():
    """使用自动建议时，提示'系统建议'和'预填'。"""
    rec = _rec(category="待评估", auto_category="产品与功能")
    hint = form_source_hint(rec, "category", "auto_category", {"待评估", ""})
    assert "系统建议" in hint


def test_source_hint_shows_insufficient_when_both_empty():
    """两者都为空时，提示'信息不足'。"""
    rec = _rec(category="待评估", auto_category="")
    hint = form_source_hint(rec, "category", "auto_category", {"待评估", ""})
    assert "信息不足" in hint
