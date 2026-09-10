"""测试：Benchmark 匹配器"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from services.benchmark_matcher import match_result_to_events, evaluate_recall, load_benchmark


def _events():
    return load_benchmark("Tavily")


def _result(url, title="", summary=""):
    return {"source_url": url, "title": title, "summary": summary, "raw_content": ""}


def test_exact_url_match():
    events = _events()
    r = _result("https://www.tavily.com/blog/What-keyless-search-really-means-for-your-data")
    event_id, match_type, score = match_result_to_events(r, events)
    assert match_type == "exact_url"
    assert event_id == "tavily_keyless_search_20260714"
    assert score == 1.0


def test_domain_keyword_match():
    events = _events()
    r = _result(
        "https://docs.tavily.com/documentation/integrations/nemo-deepagents",
        title="NVIDIA NemoClaw Deep Agents integration with Tavily"
    )
    event_id, match_type, score = match_result_to_events(r, events)
    assert event_id == "tavily_nemoclaws_integration_20260716"


def test_title_keyword_match():
    events = _events()
    r = _result(
        "https://somesite.com/article",
        title="Tavily x Composio Dev Cup hackathon event",
    )
    event_id, match_type, score = match_result_to_events(r, events)
    assert event_id == "tavily_composio_dev_cup_20260717"


def test_github_topics_does_not_match_specific_update():
    """GitHub Topics 页面不误匹配 tavily-mcp 版本更新。"""
    events = _events()
    r = _result(
        "https://github.com/topics/tavily",
        title="tavily - GitHub Topics",
    )
    event_id, match_type, score = match_result_to_events(r, events)
    assert event_id is None or match_type in ("no_match", "title_keyword")


def test_tavily_homepage_not_match_keyless_search():
    """Tavily 官网首页不误匹配 Keyless Search Blog。"""
    events = _events()
    r = _result("https://tavily.com", title="Tavily AI Search")
    event_id, _, _ = match_result_to_events(r, events)
    assert event_id != "tavily_keyless_search_20260714"


def test_third_party_mcp_review_not_match_official_mcp():
    """第三方 MCP 评测不误匹配官方 tavily-mcp 版本更新。"""
    events = _events()
    r = _result(
        "https://mcpshowcase.com/servers/tavily",
        title="Tavily on MCP Showcase",
    )
    event_id, _, _ = match_result_to_events(r, events)
    # 不应匹配 tavily_mcp_timeout_20260710
    assert event_id != "tavily_mcp_timeout_20260710"


def test_recall_rate_calculation():
    """4 条全部召回 → 100%；3 条 → 75%。"""
    events = _events()
    full_results = [
        _result("https://www.tavily.com/blog/What-keyless-search-really-means-for-your-data"),
        _result("https://luma.com/tavily-h550", title="Tavily Composio Dev Cup event"),
        _result("https://docs.tavily.com/documentation/integrations/nemo-deepagents",
                title="NVIDIA NemoClaw Deep Agents integration"),
        _result("https://github.com/tavily-ai/tavily-mcp/commits/main",
                title="tavily-mcp 0.2.21 Research streaming timeout update"),
    ]
    r_full = evaluate_recall(full_results, "Tavily")
    assert r_full["recall_rate"] == 1.0

    r_partial = evaluate_recall(full_results[:3], "Tavily")
    assert r_partial["recall_rate"] == pytest.approx(0.75, abs=0.01)


import pytest
