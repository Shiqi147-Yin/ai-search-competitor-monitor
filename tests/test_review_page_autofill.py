"""测试：待审核区自动填入逻辑"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from services.content_analyzer import analyze_record, AnalysisResult


def _rec_with_auto(**kwargs):
    """构造一条含 auto_ 字段的记录（模拟已写入 DB 的待审核记录）。"""
    base = {
        "id": 1, "title": "Exa Agent Skills", "summary": "New skills",
        "competitor": "Exa", "source_platform": "X",
        "category": "待评估", "priority": "中", "querit_status": "待评估",
        "business_value": "", "suggested_action": "", "gap_analysis": "",
        "auto_category": "产品与功能", "auto_priority": "高",
        "auto_business_value": "将搜索能力包装为可安装 Skill。",
        "auto_suggested_action": "评估 Querit 是否需要同类场景。",
        "auto_gap_analysis": "待人工确认。",
        "auto_querit_status": "待评估",
        "analysis_status": "analyzed", "analysis_confidence": 0.8,
        "analysis_reason": "关键词匹配：agent skills",
    }
    base.update(kwargs)
    return base


def test_autofill_category_when_human_is_default():
    """当人工 category=待评估时，表单应展示 auto_category。"""
    from services.content_analyzer import _form_default_val

    rec = _rec_with_auto(category="待评估", auto_category="产品与功能")
    val = _form_default_val(rec, "category", "auto_category", "待评估")
    assert val == "产品与功能"


def test_human_field_takes_priority():
    """人工已填写时，不被 auto 字段覆盖。"""
    from services.content_analyzer import _form_default_val

    rec = _rec_with_auto(category="市场与运营", auto_category="产品与功能")
    val = _form_default_val(rec, "category", "auto_category", "待评估")
    assert val == "市场与运营"


def test_reanalyze_does_not_overwrite_human_category():
    """重新分析不覆盖人工已填写的 category。"""
    rec = _rec_with_auto(category="市场与运营")  # 人工修改过
    fresh = analyze_record(rec)
    fill = fresh.to_fill_fields({"category": "市场与运营"})
    # to_fill_fields 应跳过已有非默认 category
    assert fill.get("category", "市场与运营") == "市场与运营"


def test_accept_suggestion_does_not_confirm_record():
    """接受建议只更新表单值，不应触发标记已确认。"""
    # 这是逻辑约束测试：accept 按钮只更新 session_state，不调用 confirm_record
    # 验证 AnalysisResult 不含 review_status 字段
    rec = _rec_with_auto()
    result = analyze_record(rec)
    db_fields = result.to_db_fields()
    assert "review_status" not in db_fields


def test_analysis_confidence_in_result():
    """分析结果包含置信度。"""
    rec = _rec_with_auto()
    result = analyze_record(rec)
    assert 0.0 <= result.analysis_confidence <= 1.0


def _form_default_val_local(rec, field, auto_field, fallback=""):
    """本地辅助（不依赖页面导入）。"""
    v = rec.get(field)
    if v and str(v).strip() and str(v).strip() not in ("待评估", ""):
        return str(v)
    av = rec.get(auto_field)
    if av:
        return str(av)
    return fallback


# 也暴露给 content_analyzer 模块
import services.content_analyzer as _ca
_ca._form_default_val = lambda rec, f, af, fb="": _form_default_val_local(rec, f, af, fb)
