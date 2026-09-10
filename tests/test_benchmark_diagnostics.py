"""测试：漏召回诊断服务"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
from unittest.mock import patch


def _make_result(url, title):
    from services.querit_client import SearchResult
    return SearchResult(url=url, title=title, rank=1, query="test",
                        raw_source="", raw_metadata={})


def _mock_found(target_url, target_title):
    """search 返回包含目标的结果。"""
    def _fn(q, n=5):
        from services.querit_client import SearchRunResult
        return SearchRunResult(
            query=q,
            results=[_make_result(target_url, target_title)],
            success=True, is_mock=True,
        )
    return _fn


def _mock_not_found(q, n=5):
    from services.querit_client import SearchResult, SearchRunResult
    return SearchRunResult(
        query=q,
        results=[_make_result("https://unrelated.com/page", "Unrelated Page")],
        success=True, is_mock=True,
    )


def _make_event(event_id="test_ev", title="Test Event",
                url="https://docs.tavily.com/docs/test",
                domains=None, keywords=None):
    return {
        "id": event_id,
        "title": title,
        "primary_url": url,
        "expected_domains": domains or ["docs.tavily.com"],
        "keywords": keywords or ["test", "event"],
    }


# ── 1. 精确 Query 找到目标 → query_strategy_issue ──────────────
def test_exact_only_found_is_query_strategy_issue():
    call_count = {"n": 0}

    def _mixed(q, n=5):
        call_count["n"] += 1
        if call_count["n"] == 1:   # title_exact 找到
            return _mock_found("https://docs.tavily.com/docs/test", "Test Event")(q, n)
        return _mock_not_found(q, n)

    from services.benchmark_diagnostics import diagnose_missed_event
    event = _make_event()
    with patch("services.benchmark_diagnostics.search", side_effect=_mixed):
        diag = diagnose_missed_event(event, num_results=3)

    assert diag.final_diagnosis == "query_strategy_issue"


# ── 2. 三种均找不到 → probable_index_coverage_gap ──────────────
def test_all_three_miss_is_index_gap():
    from services.benchmark_diagnostics import diagnose_missed_event
    event = _make_event(
        url="https://www.tavily.com/blog/What-keyless-search-really-means-for-your-data"
    )
    with patch("services.benchmark_diagnostics.search", side_effect=_mock_not_found):
        diag = diagnose_missed_event(event, num_results=3)

    assert diag.final_diagnosis == "probable_index_coverage_gap"


# ── 3. API 返回目标但匹配器之前未命中 → benchmark_matching_issue ─
def test_api_returns_target_all_variants_is_benchmark_issue():
    from services.benchmark_diagnostics import diagnose_missed_event
    event = _make_event(url="https://luma.com/tavily-h550",
                        title="Dev Cup: Tavily x Composio",
                        domains=["luma.com"])

    def _all_found(q, n=5):
        return _mock_found("https://luma.com/tavily-h550",
                            "Dev Cup: Tavily x Composio developer event")(q, n)

    with patch("services.benchmark_diagnostics.search", side_effect=_all_found):
        diag = diagnose_missed_event(event, num_results=3)

    assert diag.final_diagnosis == "benchmark_matching_issue"


# ── 4. 诊断模式不写数据库 ────────────────────────────────────────
def test_diagnose_does_not_write_database(tmp_path, monkeypatch):
    import config, database
    tmp_db = tmp_path / "diag_no_write.db"
    monkeypatch.setattr(config, "DB_PATH", tmp_db)
    monkeypatch.setattr(database, "DB_PATH", tmp_db)
    database.init_db()
    database.run_migrations()

    from services.benchmark_diagnostics import diagnose_missed_event
    event = _make_event()
    with patch("services.benchmark_diagnostics.search", side_effect=_mock_not_found):
        diagnose_missed_event(event, num_results=1)

    assert len(database.get_records()) == 0


# ── 5. 单个事件失败不影响其他 ─────────────────────────────────────
def test_single_event_failure_does_not_affect_others():
    call_count = {"n": 0}

    def _fails_first_event(q, n=5):
        call_count["n"] += 1
        if call_count["n"] <= 3:
            raise RuntimeError("Simulated error")
        return _mock_not_found(q, n)

    from services.benchmark_diagnostics import diagnose_all_missed
    with patch("services.benchmark_diagnostics.search", side_effect=_fails_first_event):
        results = diagnose_all_missed("Tavily", missed_ids=[
            "tavily_keyless_search_20260714",
            "tavily_composio_dev_cup_20260717",
        ])

    assert len(results) == 2
    # 第一个有异常 → unknown，第二个仍有诊断
    assert results[0].final_diagnosis in ("unknown", "probable_index_coverage_gap")
    assert results[1].final_diagnosis is not None


# ── 6. 结果数量正确记录 ───────────────────────────────────────────
def test_variant_result_count_recorded():
    from services.querit_client import SearchResult, SearchRunResult
    from services.benchmark_diagnostics import diagnose_missed_event

    def _three_results(q, n=5):
        return SearchRunResult(
            query=q,
            results=[_make_result(f"https://example.com/{i}", f"Result {i}") for i in range(3)],
            success=True, is_mock=True,
        )

    event = _make_event()
    with patch("services.benchmark_diagnostics.search", side_effect=_three_results):
        diag = diagnose_missed_event(event, num_results=5)

    assert all(v.result_count == 3 for v in diag.variants)


# ── 7. API 失败时诊断为 unknown ──────────────────────────────────
def test_api_failure_gives_unknown_diagnosis():
    from services.querit_client import SearchRunResult
    from services.benchmark_diagnostics import diagnose_missed_event

    def _fail_api(q, n=5):
        return SearchRunResult(query=q, error="Connection error", success=False)

    event = _make_event()
    with patch("services.benchmark_diagnostics.search", side_effect=_fail_api):
        diag = diagnose_missed_event(event, num_results=3)

    assert diag.final_diagnosis == "unknown"
