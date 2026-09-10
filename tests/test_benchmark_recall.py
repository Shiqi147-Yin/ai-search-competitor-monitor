"""测试：Benchmark 召回率计算"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
from services.benchmark_matcher import evaluate_recall, load_benchmark


def _r(url, title="", summary=""):
    return {"source_url": url, "title": title, "summary": summary, "raw_content": ""}


_ALL_EXPECTED = [
    _r("https://www.tavily.com/blog/What-keyless-search-really-means-for-your-data",
       title="What keyless search really means for your data"),
    _r("https://luma.com/tavily-h550",
       title="Tavily Composio Dev Cup developer event"),
    _r("https://docs.tavily.com/documentation/integrations/nemo-deepagents",
       title="NVIDIA NemoClaw Deep Agents Tavily integration"),
    _r("https://github.com/tavily-ai/tavily-mcp/commits/main",
       title="tavily-mcp 0.2.21 Research streaming timeout fix"),
]


def test_recall_100_percent():
    result = evaluate_recall(_ALL_EXPECTED, "Tavily")
    assert result["recall_rate"] == 1.0
    assert result["recalled_count"] == 4
    assert result["missed_count"] == 0


def test_recall_75_percent():
    result = evaluate_recall(_ALL_EXPECTED[:3], "Tavily")
    assert result["recall_rate"] == pytest.approx(0.75, abs=0.01)
    assert result["missed_count"] == 1


def test_different_channels_not_double_counted():
    """同一事件从两个渠道召回，不计两次。"""
    results = [
        _r("https://luma.com/tavily-h550", title="Tavily Composio Dev Cup"),
        _r("https://x.com/TavilyHQ/status/999",
           title="Tavily x Composio Dev Cup developer event hackathon"),
    ]
    result = evaluate_recall(results, "Tavily")
    composio_events = [e for e in result["recalled_events"]
                       if "composio" in e]
    assert len(composio_events) <= 1


def test_missed_events_list_correct():
    only_keyless = [
        _r("https://www.tavily.com/blog/What-keyless-search-really-means-for-your-data")
    ]
    result = evaluate_recall(only_keyless, "Tavily")
    assert result["missed_count"] == 3
    missed_ids = {e["id"] for e in result["missed_events"]}
    assert "tavily_composio_dev_cup_20260717" in missed_ids
    assert "tavily_nemoclaws_integration_20260716" in missed_ids
    assert "tavily_mcp_timeout_20260710" in missed_ids
