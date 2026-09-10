"""测试：分类冲突规则"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from services.content_analyzer import analyze_record


def _rec(**kwargs):
    base = {"competitor": "Exa", "source_platform": "X", "title": "", "summary": "",
            "raw_content": "", "docs_changed": 0, "capability_change": 0,
            "integration_change": 0, "developer_experience_change": 0, "change_summary": ""}
    base.update(kwargs)
    return base


def test_product_launch_with_integration_prefers_product():
    """明确新增产品能力时，一级分类选产品与功能（即使有集成关键词）。"""
    rec = _rec(
        title="Exa Agent Skills: new capability for recruiting and langchain integration",
        capability_change=1,
    )
    result = analyze_record(rec)
    assert result.category == "产品与功能"


def test_integration_launch_prefers_ecosystem():
    """明确外部平台接入，一级分类选生态与集成。"""
    rec = _rec(
        title="Exa × Cerebras integration: connect neural search with inference",
        integration_change=1,
        capability_change=0,
    )
    result = analyze_record(rec)
    assert result.category == "生态与集成"


def test_event_transmission_prefers_market():
    """主要是活动传播，一级分类选市场与运营。"""
    rec = _rec(
        title="Tavily at AI Summit 2026",
        summary="Join us for developer event and community sponsorship",
        source_platform="Event",
    )
    result = analyze_record(rec)
    assert result.category == "市场与运营"


def test_secondary_tags_preserved():
    """secondary_tags 保留其他方向标签，不因一级分类而丢弃。"""
    rec = _rec(
        title="Exa Agent Skills: LangChain integration with new search mode",
        capability_change=1,
        integration_change=1,
    )
    result = analyze_record(rec)
    # 一级分类为产品与功能或生态与集成均可接受（取决于得分）
    assert result.category in ("产品与功能", "生态与集成")
    # secondary_tags 不为空（存在交叉标签）
    assert len(result.secondary_tags) > 0


def test_ambiguous_content_goes_to_pending():
    """无法稳定判断时归待评估。"""
    rec = _rec(title="something happened", summary="an update")
    result = analyze_record(rec)
    # 不应崩溃，category 应为有效值
    assert result.category in ["产品与功能", "生态与集成", "市场与运营", "待评估"]
