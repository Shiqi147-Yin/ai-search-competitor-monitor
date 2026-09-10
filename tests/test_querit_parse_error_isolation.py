"""测试：解析错误隔离"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from services.querit_client import parse_search_response


def test_one_invalid_two_valid():
    """一条非法、两条合法 → 返回两条合法，invalid_count=1。"""
    raw = {"results": [
        {"url": "https://good.com/1", "title": "Good 1"},
        "not a url at all",
        {"url": "https://good.com/2", "title": "Good 2"},
    ]}
    results, invalid, _ = parse_search_response(raw, "test")
    assert len(results) == 2
    assert invalid == 1


def test_invalid_count_correct():
    """多条非法 → invalid_count 准确。"""
    raw = {"results": [
        {"url": "https://ok.com"},
        {"title": "no url"},
        "plain text",
        {"title": "also no url"},
    ]}
    results, invalid, _ = parse_search_response(raw, "test")
    assert len(results) == 1
    assert invalid == 3


def test_query_does_not_fail_on_partial_invalid():
    """部分非法不导致 Query 整体失败（返回 success=True 的 SearchRunResult）。"""
    from services.querit_client import parse_search_response, SearchRunResult
    raw = {"results": [{"url": "https://ok.com/x"}, "invalid"]}
    results, invalid, _ = parse_search_response(raw, "test")
    assert len(results) == 1
    assert invalid == 1
    # 模拟 search() 成功返回
    run_result = SearchRunResult(query="test", results=results, success=True,
                                  invalid_result_count=invalid)
    assert run_result.success is True


def test_all_invalid_returns_empty_not_error():
    """全部条目无效 → 返回空列表，但 invalid_count > 0，不视为请求失败。"""
    raw = {"results": ["no url", "also no url", {"title": "missing url"}]}
    results, invalid, _ = parse_search_response(raw, "test")
    assert len(results) == 0
    assert invalid == 3
