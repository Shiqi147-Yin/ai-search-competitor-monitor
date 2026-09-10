"""测试：fetch_status 置信度上限"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from services.content_analyzer import analyze_record, _FETCH_STATUS_CAPS


def _rec(fetch_status="success", title="Exa streaming search API released",
         summary="New streaming search mode with low latency.", raw_content="",
         **kwargs):
    base = {
        "competitor": "Exa", "source_platform": "X",
        "title": title, "summary": summary, "raw_content": raw_content,
        "fetch_status": fetch_status, "fetch_error": "",
        "source_url": "https://x.com/ExaDevelopers/status/123",
        "capability_change": 0, "integration_change": 0,
        "docs_changed": 0, "developer_experience_change": 0, "change_summary": "",
    }
    base.update(kwargs)
    return base


def test_success_cap_allows_high_confidence():
    """success 记录可以达到高置信度（上限 1.0）。"""
    rec = _rec(
        fetch_status="success",
        title="Exa streaming search API released with MCP support",
        summary="New streaming API with MCP server and agent skills.",
        raw_content="We are releasing streaming search with mcp support and agent skills integration." * 5,
    )
    result = analyze_record(rec)
    assert result.analysis_confidence <= _FETCH_STATUS_CAPS["success"]
    assert result.analysis_confidence >= 0.7


def test_partial_cap_is_070():
    """partial 记录置信度不超过 0.70。"""
    rec = _rec(
        fetch_status="partial",
        title="Exa streaming search API released",
        summary="New streaming mode.",
        raw_content="streaming search mode " * 50,
    )
    result = analyze_record(rec)
    assert result.analysis_confidence <= 0.70, f"partial 置信度 {result.analysis_confidence} 超过 0.70"


def test_restricted_cap_is_040():
    """restricted 记录置信度不超过 0.40。"""
    rec = _rec(
        fetch_status="restricted",
        title="Exa streaming search API",
        summary="streaming search released",
        raw_content="streaming api released " * 50,
    )
    result = analyze_record(rec)
    assert result.analysis_confidence <= 0.40, f"restricted 置信度 {result.analysis_confidence} 超过 0.40"


def test_failed_cap_is_025():
    """failed 记录置信度不超过 0.25。"""
    rec = _rec(
        fetch_status="failed",
        title="Exa streaming search API",
        summary="streaming",
        raw_content="streaming api " * 50,
    )
    result = analyze_record(rec)
    assert result.analysis_confidence <= 0.25, f"failed 置信度 {result.analysis_confidence} 超过 0.25"


def test_final_confidence_is_min_of_both():
    """最终置信度 = min(内容基础分, fetch_status 上限)。"""
    # partial + 丰富内容：内容基础分可能 0.9，但 partial 上限 0.70
    rec = _rec(
        fetch_status="partial",
        title="Exa MCP server released",
        summary="New MCP server for coding agents.",
        raw_content="new mcp server for coding agents with oauth and streaming search. " * 20,
    )
    result = analyze_record(rec)
    assert result.analysis_confidence <= 0.70


def test_fetch_status_caps_dict_coverage():
    """_FETCH_STATUS_CAPS 包含所有关键状态。"""
    for s in ("success", "partial", "restricted", "failed"):
        assert s in _FETCH_STATUS_CAPS
        assert 0 <= _FETCH_STATUS_CAPS[s] <= 1.0
