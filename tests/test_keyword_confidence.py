"""测试：单关键词置信度不得虚高"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from services.content_analyzer import analyze_record


def _rec(title="", source_url="", fetch_status="success", **kwargs):
    base = {
        "competitor": "Exa", "source_platform": "LinkedIn",
        "title": title, "summary": "", "raw_content": "",
        "fetch_status": fetch_status, "fetch_error": "",
        "source_url": source_url,
        "capability_change": 0, "integration_change": 0,
        "docs_changed": 0, "developer_experience_change": 0, "change_summary": "",
    }
    base.update(kwargs)
    return base


def test_only_summit_in_url_below_040():
    """仅 URL 中含 summit，无标题无正文，置信度不超过 0.40。"""
    rec = _rec(source_url="https://linkedin.com/posts/exa-summit-2026",
               fetch_status="restricted", fetch_error="HTTP 451")
    result = analyze_record(rec)
    assert result.analysis_confidence <= 0.40


def test_only_activity_in_url_below_040():
    """仅 URL 中含 activity 词，无内容，置信度不超过 0.40。"""
    rec = _rec(source_url="https://linkedin.com/posts/exa-ai-activity-123",
               fetch_status="restricted", fetch_error="HTTP 451")
    result = analyze_record(rec)
    assert result.analysis_confidence <= 0.40


def test_full_content_with_clear_keywords_above_080():
    """完整标题+正文+明确关键词可达到 0.80 以上。"""
    rec = {
        "competitor": "Exa", "source_platform": "X",
        "title": "Exa releases new streaming search API with MCP support",
        "summary": "New streaming API released with mcp server and agent skills.",
        "raw_content": ("We are releasing a new streaming search API with mcp support "
                        "and agent skills. npx skills add exa-labs/agent-skills. ") * 10,
        "fetch_status": "success", "fetch_error": "",
        "source_url": "https://x.com/ExaDevelopers/status/123",
        "capability_change": 1, "integration_change": 0,
        "docs_changed": 0, "developer_experience_change": 0, "change_summary": "",
    }
    result = analyze_record(rec)
    assert result.analysis_confidence >= 0.80, (
        f"置信度 {result.analysis_confidence} 低于 0.80"
    )


def test_single_event_keyword_in_title_not_high():
    """标题只有 event 一个词，置信度不超过 0.60（受内容充足性约束）。"""
    rec = _rec(title="Developer event", fetch_status="success")
    result = analyze_record(rec)
    # 只有标题，content_cap=0.59；event 是市场关键词
    assert result.analysis_confidence <= 0.60


def test_restricted_with_title_stays_below_040():
    """restricted 记录即使有标题，置信度仍不超过 0.40。"""
    rec = _rec(
        title="Exa at RAISE Summit 2026",
        fetch_status="restricted",
        fetch_error="HTTP 403",
        source_url="https://linkedin.com/posts/exa-raise-summit",
    )
    result = analyze_record(rec)
    assert result.analysis_confidence <= 0.40
