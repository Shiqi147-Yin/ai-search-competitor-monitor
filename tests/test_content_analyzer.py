"""测试：自动内容分析器"""
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


def test_agent_skills_is_product_feature():
    """Agent Skills → 产品与功能"""
    rec = _rec(
        title="Exa Agent Skills: Recruit, sell, and research with AI",
        summary="Exa launches installable Agent Skills for recruiting, sales, and research.",
        capability_change=1,
    )
    result = analyze_record(rec)
    assert result.category == "产品与功能"


def test_cerebras_integration_is_ecosystem():
    """Cerebras integration → 生态与集成"""
    rec = _rec(
        title="Exa × Cerebras: Fast inference meets neural search",
        summary="New integration with Cerebras for high-speed inference and search.",
        integration_change=1,
    )
    result = analyze_record(rec)
    assert result.category == "生态与集成"


def test_event_summit_is_market():
    """Event / Summit → 市场与运营"""
    rec = _rec(
        title="Tavily developer summit 2026",
        summary="Join us for the annual developer event and community meetup.",
        source_platform="Event",
    )
    result = analyze_record(rec)
    assert result.category == "市场与运营"


def test_insufficient_content_is_pending():
    """内容不足 → 待评估"""
    rec = _rec(title="", summary="", source_platform="X")
    result = analyze_record(rec)
    assert result.category == "待评估"


def test_business_value_not_empty():
    """business_value 不为空（对有内容的记录）。"""
    rec = _rec(
        title="Exa Agent Skills launch",
        summary="New agent skills for recruiting and research",
        capability_change=1,
    )
    result = analyze_record(rec)
    assert result.business_value and len(result.business_value) > 10


def test_suggested_action_not_empty():
    """suggested_action 不为空。"""
    rec = _rec(title="LangChain + Exa integration", summary="New connector for langchain.")
    result = analyze_record(rec)
    assert result.suggested_action and len(result.suggested_action) > 5


def test_querit_status_default_pending():
    """querit_status 默认为待评估，不自动标记已覆盖。"""
    rec = _rec(title="Tavily streaming API released", capability_change=1)
    result = analyze_record(rec)
    assert result.querit_status == "待评估"
    assert result.auto_querit_status == "待评估"


def test_analysis_does_not_crash_on_empty():
    """全空记录不崩溃。"""
    result = analyze_record({})
    assert result.category == "待评估"
    assert result.analysis_status in ("partial", "failed", "analyzed")


def test_github_capability_change_classified_product():
    """GitHub capability_change=1 → 产品与功能。"""
    rec = _rec(
        source_platform="GitHub",
        title="Add streaming search mode",
        capability_change=1,
        change_summary="New streaming API endpoint with MCP support",
    )
    result = analyze_record(rec)
    assert result.category == "产品与功能"
