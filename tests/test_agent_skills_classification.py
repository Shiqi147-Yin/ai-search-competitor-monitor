"""测试：Exa Agent Skills 分类准确性"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from services.content_analyzer import analyze_record


def _agent_skills_rec(**kwargs):
    base = {
        "competitor": "Exa", "source_platform": "X",
        "title": "We're releasing a set of skills that we use internally at Exa",
        "summary": (
            "We use these skills across GTM, Recruiting, and Engineering. "
            "npx skills add exa-labs/agent-skills"
        ),
        "raw_content": (
            "We're releasing a set of skills that we use internally at Exa across GTM, "
            "Recruiting, and Engineering. Use them with Composio. "
            "npx skills add exa-labs/agent-skills"
        ),
        "capability_change": 0, "integration_change": 0,
        "docs_changed": 0, "developer_experience_change": 0,
        "change_summary": "", "fetch_status": "success",
    }
    base.update(kwargs)
    return base


def test_agent_skills_is_product_feature():
    """Exa Agent Skills → 产品与功能（不能归为待评估）。"""
    rec = _agent_skills_rec()
    result = analyze_record(rec)
    assert result.category == "产品与功能", (
        f"期望产品与功能，实际 {result.category}。"
        f"reason: {result.analysis_reason}"
    )


def test_agent_skills_secondary_tags_include_agent_skills():
    """secondary_tags 至少包含 Agent Skills。"""
    rec = _agent_skills_rec()
    result = analyze_record(rec)
    tag_str = " ".join(result.secondary_tags).lower()
    assert "agent skills" in tag_str or "Agent Skills" in result.secondary_tags


def test_agent_skills_npx_install_boosts_confidence():
    """含 npx skills add 安装命令时，置信度 >= 0.8。"""
    rec = _agent_skills_rec()
    result = analyze_record(rec)
    assert result.analysis_confidence >= 0.8, (
        f"置信度 {result.analysis_confidence} 低于 0.8。reason: {result.analysis_reason}"
    )


def test_agent_skills_not_pending():
    """Exa Agent Skills 不能归为待评估。"""
    rec = _agent_skills_rec()
    result = analyze_record(rec)
    assert result.category != "待评估"


def test_agent_skills_analysis_reason_mentions_keyword():
    """analysis_reason 应包含有关 Agent Skills 的说明。"""
    rec = _agent_skills_rec()
    result = analyze_record(rec)
    reason_lower = result.analysis_reason.lower()
    # 原因里应提及强信号关键词
    assert any(kw in reason_lower for kw in ["agent skills", "skills add", "npx skills", "强信号"])


def test_agent_skills_priority_is_medium_or_high():
    """优先级应为中或高。"""
    rec = _agent_skills_rec()
    result = analyze_record(rec)
    assert result.priority in ("中", "高")
