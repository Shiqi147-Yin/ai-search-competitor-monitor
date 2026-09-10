"""测试：各种真实响应形状"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from services.querit_client import parse_search_response


def _run(raw):
    results, invalid, path = parse_search_response(raw, "test")
    return results, invalid, path


def test_results_shape():
    r, _, p = _run({"results": [{"url": "https://a.com", "title": "A"}]})
    assert len(r) == 1 and p == "results"


def test_data_shape():
    r, _, p = _run({"data": [{"url": "https://b.com"}]})
    assert len(r) == 1 and p == "data"


def test_items_shape():
    r, _, p = _run({"items": [{"url": "https://c.com"}]})
    assert len(r) == 1 and p == "items"


def test_nested_data_results_shape():
    r, _, p = _run({"data": {"results": [{"url": "https://d.com"}]}})
    assert len(r) == 1


def test_string_list_shape():
    r, inv, _ = _run({"results": ["https://e.com", "plain text no url"]})
    assert len(r) == 1
    assert inv == 1


def test_querit_nested_result_shape():
    """Querit 真实格式：results.result。"""
    r, _, p = _run({"results": {"result": [{"url": "https://f.com", "title": "F"}]}})
    assert len(r) == 1
    assert p == "results.result"
