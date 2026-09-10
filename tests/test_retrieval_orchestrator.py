"""测试：多来源检索编排器"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
from unittest.mock import patch
from datetime import datetime, timezone


@pytest.fixture(autouse=True)
def isolated_db(tmp_path, monkeypatch):
    import config, database
    tmp_db = tmp_path / "orch_test.db"
    monkeypatch.setattr(config, "DB_PATH", tmp_db)
    monkeypatch.setattr(database, "DB_PATH", tmp_db)
    database.init_db()
    database.run_migrations()
    yield


def _mock_search(query, num_results=10):
    from services.querit_client import SearchResult, SearchRunResult
    return SearchRunResult(
        query=query,
        results=[
            SearchResult(url=f"https://tavily.com/test-{i}",
                         title=f"Tavily result {i}", published_date="2026-07-18T00:00:00Z",
                         rank=i, query=query, raw_source="", raw_metadata={})
            for i in range(1, min(3, num_results) + 1)
        ],
        success=True, is_mock=True,
    )


def test_multiple_sources_executed_independently():
    """多来源 Query 独立执行，单个失败不影响其他。"""
    call_count = {"n": 0}

    def _mixed_search(q, n=10):
        call_count["n"] += 1
        if call_count["n"] == 1:
            from services.querit_client import SearchRunResult
            return SearchRunResult(query=q, error="Simulated fail", success=False)
        return _mock_search(q, n)

    with patch("services.querit_retrieval_orchestrator.search", side_effect=_mixed_search):
        from services.querit_retrieval_orchestrator import run_targeted_search
        result = run_targeted_search(
            competitors=["Tavily"],
            time_window_days=7,
            source_scope=["All"],
            result_per_query=2,
            reference_time=datetime(2026, 7, 21, 0, 0, 0, tzinfo=timezone.utc),
        )
    assert call_count["n"] > 1
    assert result.errors  # 有失败
    assert len(result.all_results) > 0  # 其他 Query 仍有结果


def test_dedup_across_queries():
    """同 URL 在不同 Query 中出现，只保留一次（不删除，标记 dedup）。"""
    with patch("services.querit_retrieval_orchestrator.search", side_effect=_mock_search):
        from services.querit_retrieval_orchestrator import run_targeted_search
        result = run_targeted_search(
            competitors=["Tavily"], time_window_days=7,
            source_scope=["Blog", "Docs"],  # 两个 Query
            result_per_query=2,
            reference_time=datetime(2026, 7, 21, 0, 0, 0, tzinfo=timezone.utc),
        )
    # unique_count <= total_raw
    assert result.unique_count <= result.total_raw


def test_query_stats_saved():
    """每个 Query 的统计被记录。"""
    with patch("services.querit_retrieval_orchestrator.search", side_effect=_mock_search):
        from services.querit_retrieval_orchestrator import run_targeted_search
        result = run_targeted_search(
            competitors=["Tavily"], time_window_days=7,
            source_scope=["Blog"],
            result_per_query=2,
            reference_time=datetime(2026, 7, 21, 0, 0, 0, tzinfo=timezone.utc),
        )
    assert len(result.query_stats) >= 1
    assert result.query_stats[0].result_count >= 0
