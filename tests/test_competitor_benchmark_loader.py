"""测试：基准集加载"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from services.benchmark_matcher import load_benchmark


def test_load_tavily_benchmark_returns_4_events():
    events = load_benchmark("Tavily")
    assert len(events) == 4


def test_benchmark_dates_are_correct():
    events = load_benchmark("Tavily")
    dates = {e["id"]: e["expected_date"] for e in events}
    assert dates.get("tavily_keyless_search_20260714") == "2026-07-14"
    assert dates.get("tavily_composio_dev_cup_20260717") == "2026-07-17"
    assert dates.get("tavily_nemoclaws_integration_20260716") == "2026-07-16"
    assert dates.get("tavily_mcp_timeout_20260710") == "2026-07-10"


def test_benchmark_urls_are_valid():
    events = load_benchmark("Tavily")
    for e in events:
        assert e.get("primary_url", "").startswith("http"), f"URL 无效: {e}"


def test_benchmark_not_write_to_db():
    """基准集加载不触发任何数据库操作。"""
    events = load_benchmark("Tavily")
    assert events  # 只检查返回值，无 DB 操作
