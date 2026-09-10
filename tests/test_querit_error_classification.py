"""测试：错误分类"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
from unittest.mock import patch, MagicMock
from services.querit_client import parse_search_response


def test_http_error_is_request_failed(monkeypatch):
    """HTTP 请求失败 → success=False, error 说明 HTTP 错误。"""
    monkeypatch.setenv("QUERIT_MOCK_MODE", "false")
    monkeypatch.setenv("QUERIT_API_KEY", "fake")
    monkeypatch.setenv("QUERIT_API_BASE_URL", "https://api.example.com")
    monkeypatch.setenv("QUERIT_API_MAX_RETRIES", "0")
    import importlib, config, services.querit_client as c
    importlib.reload(config)
    importlib.reload(c)
    mock_resp = MagicMock()
    mock_resp.status_code = 500
    with patch("services.querit_client._requests.post", return_value=mock_resp):
        result = c.search("test", 1)
    assert result.success is False
    assert "500" in result.error or "服务端" in result.error


def test_json_parse_failure_is_response_invalid(monkeypatch):
    """响应 JSON 解析失败 → success=False, error 说明解析失败。"""
    monkeypatch.setenv("QUERIT_MOCK_MODE", "false")
    monkeypatch.setenv("QUERIT_API_KEY", "fake")
    monkeypatch.setenv("QUERIT_API_BASE_URL", "https://api.example.com")
    monkeypatch.setenv("QUERIT_API_MAX_RETRIES", "0")
    import importlib, config, services.querit_client as c
    importlib.reload(config)
    importlib.reload(c)
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.side_effect = ValueError("not json")
    with patch("services.querit_client._requests.post", return_value=mock_resp):
        result = c.search("test", 1)
    assert result.success is False
    assert "解析失败" in result.error or "JSON" in result.error


def test_empty_results_is_completed_not_failed():
    """响应成功但结果为空 → success=True, 结果列表为空。"""
    results, invalid, path = parse_search_response({"results": []}, "test")
    assert results == []
    assert invalid == 0


def test_attribute_error_does_not_appear_as_connection_error():
    """AttributeError 不再被包装成连接错误（隔离在 _parse_single_item 内）。"""
    # 旧 parse_search_response 对 str 调用 .get() 会触发 AttributeError
    # 新版本应安全处理
    raw = {"results": ["string item that caused old AttributeError"]}
    results, invalid, _ = parse_search_response(raw, "test")
    # 不抛 AttributeError
    assert isinstance(results, list)


def test_unrecognized_structure_returns_empty():
    """完全无法识别的结构 → 返回空列表，不崩溃。"""
    raw = {"unknown_key": "unknown_value"}
    results, invalid, path = parse_search_response(raw, "test")
    assert results == []
    assert path == "未找到"
