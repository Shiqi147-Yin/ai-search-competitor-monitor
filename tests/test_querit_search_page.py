"""测试：Querit 检索页面行为（逻辑层，不启动 Streamlit）"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
from services.querit_client import check_config
from services.querit_query_builder import generate_queries, is_english_query


def test_missing_config_blocks_request(monkeypatch):
    """API Key 缺失时 check_config 返回 False（非 Mock 模式）。"""
    monkeypatch.setenv("QUERIT_MOCK_MODE", "false")
    monkeypatch.setenv("QUERIT_API_KEY", "")
    monkeypatch.setenv("QUERIT_API_BASE_URL", "https://api.example.com")
    import importlib
    import config as cfg
    importlib.reload(cfg)
    import services.querit_client as c
    importlib.reload(c)
    ok, err = c.check_config()
    assert not ok
    assert err


def test_query_preview_is_editable():
    """生成的 Query 可以被修改（模拟用户编辑）。"""
    queries = generate_queries(["Tavily"], 7, ["All"])
    original = queries[0]["generated_query"]
    queries[0]["generated_query"] = "Custom edited Tavily query"
    assert queries[0]["generated_query"] != original


def test_mock_mode_status():
    """Mock 模式下 is_mock=True。"""
    import os; os.environ["QUERIT_MOCK_MODE"] = "true"
    import importlib, services.querit_client as c
    importlib.reload(c)
    result = c.search("test query", 2)
    assert result.is_mock is True


def test_page_does_not_auto_import():
    """页面逻辑：未确认时不写入 competitor_updates（通过 adapter 验证）。"""
    from services.querit_result_adapter import adapt_results
    from services.querit_client import SearchResult

    r = SearchResult(url="https://tavily.com/page-test", title="Page test",
                     rank=1, query="test", raw_source="", raw_metadata={})
    adapted = adapt_results([r], "run_page", 1)
    # adapt_results 不写 DB
    import database
    records = database.get_records()
    # 在隔离环境中，不存在 competitor_updates 写入
    for rec in records:
        assert rec.get("source_url") != "https://tavily.com/page-test"


def test_query_language_is_english():
    """生成的所有 Query 均为英文。"""
    for comp in ["Tavily", "Exa", "Brave"]:
        queries = generate_queries([comp], 7, ["All"])
        for q in queries:
            assert is_english_query(q["generated_query"])
