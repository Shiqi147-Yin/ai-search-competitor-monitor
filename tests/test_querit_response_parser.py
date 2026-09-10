"""测试：Querit 响应解析器（各种结构）"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from services.querit_client import parse_search_response, SearchResult


def test_top_level_dict_results_list():
    """顶层 dict + results list。"""
    raw = {"results": [
        {"url": "https://tavily.com/a", "title": "T1", "snippet": "S1"},
    ]}
    results, invalid, path = parse_search_response(raw, "test")
    assert len(results) == 1
    assert results[0].url == "https://tavily.com/a"
    assert results[0].title == "T1"


def test_top_level_list():
    """顶层是列表。"""
    raw = [{"url": "https://exa.ai/b", "title": "T2"}]
    results, invalid, path = parse_search_response(raw, "test")
    assert len(results) == 1
    assert results[0].url == "https://exa.ai/b"


def test_querit_real_structure():
    """Querit 真实响应结构：results.result。"""
    raw = {
        "took": "1.2",
        "error_code": 0,
        "results": {
            "result": [
                {"url": "https://tavily.com/c", "title": "T3", "snippet": "S3",
                 "page_age": "2026-07-15T10:00:00Z", "site_name": "tavily.com"},
            ]
        }
    }
    results, invalid, path = parse_search_response(raw, "test")
    assert len(results) == 1
    assert results[0].url == "https://tavily.com/c"
    assert results[0].published_date == "2026-07-15T10:00:00Z"
    assert path == "results.result"


def test_data_results_nested():
    """data.results 嵌套。"""
    raw = {"data": {"results": [{"url": "https://brave.com/d", "title": "T4"}]}}
    results, invalid, path = parse_search_response(raw, "test")
    assert len(results) == 1


def test_single_dict_result():
    """单条 dict 结果。"""
    raw = {"items": [{"url": "https://example.com/e", "title": "T5"}]}
    results, invalid, path = parse_search_response(raw, "test")
    assert len(results) == 1


def test_single_url_string_item():
    """单条 URL 字符串。"""
    raw = {"results": ["https://tavily.com/url-only"]}
    results, invalid, path = parse_search_response(raw, "test")
    assert len(results) == 1
    assert results[0].url == "https://tavily.com/url-only"


def test_single_plain_text_string_skipped():
    """普通文本字符串跳过（无 URL）。"""
    raw = {"results": ["just some text without a URL"]}
    results, invalid, path = parse_search_response(raw, "test")
    assert len(results) == 0
    assert invalid == 1


def test_null_fields_handled():
    """字段为 null 不崩溃。"""
    raw = {"results": [{"url": "https://example.com/f", "title": None, "score": None}]}
    results, invalid, path = parse_search_response(raw, "test")
    assert len(results) == 1
    assert results[0].title == ""


def test_missing_url_skipped():
    """缺少 URL 的结果被跳过，invalid_count+1。"""
    raw = {"results": [{"title": "No URL here", "content": "content"}]}
    results, invalid, path = parse_search_response(raw, "test")
    assert len(results) == 0
    assert invalid == 1


def test_invalid_item_does_not_affect_others():
    """一条非法不影响其他合法结果。"""
    raw = {"results": [
        {"url": "https://good.com/1", "title": "Good"},
        "invalid plain text",
        {"url": "https://good.com/2", "title": "Good2"},
    ]}
    results, invalid, path = parse_search_response(raw, "test")
    assert len(results) == 2
    assert invalid == 1


def test_snippet_maps_to_summary():
    """snippet 字段映射到 summary。"""
    raw = {"results": [{"url": "https://example.com", "snippet": "My snippet"}]}
    results, _, _ = parse_search_response(raw, "test")
    assert results[0].summary == "My snippet"


def test_page_age_maps_to_published_date():
    """page_age 字段映射到 published_date（Querit 真实响应）。"""
    raw = {
        "results": {
            "result": [{"url": "https://example.com", "page_age": "2026-07-15T00:00:00Z"}]
        }
    }
    results, _, _ = parse_search_response(raw, "test")
    assert results[0].published_date == "2026-07-15T00:00:00Z"
