"""测试：Querit Client（使用 mock，不依赖真实 API）"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import os
import pytest
from unittest.mock import patch, MagicMock


@pytest.fixture(autouse=True)
def force_mock_mode(monkeypatch):
    """默认所有测试在 mock 模式，需要测非 mock 时由单测自行切换。"""
    monkeypatch.setenv("QUERIT_MOCK_MODE", "true")
    yield


def _reload_client(monkeypatch, mock=False, key="", base_url="", retries=0):
    """切换 mock/非 mock 模式并重载模块。"""
    monkeypatch.setenv("QUERIT_MOCK_MODE", "true" if mock else "false")
    monkeypatch.setenv("QUERIT_API_KEY", key)
    monkeypatch.setenv("QUERIT_API_BASE_URL", base_url)
    monkeypatch.setenv("QUERIT_API_MAX_RETRIES", str(retries))
    import importlib
    import config as cfg
    importlib.reload(cfg)
    import services.querit_client as c
    importlib.reload(c)
    return c


def test_mock_search_returns_results(monkeypatch):
    """Mock 模式下 search() 返回成功结果。"""
    c = _reload_client(monkeypatch, mock=True)
    result = c.search("Latest Tavily API updates", 5)
    assert result.success is True
    assert result.is_mock is True
    assert len(result.results) > 0


def test_mock_result_has_url(monkeypatch):
    """Mock 结果包含 URL。"""
    c = _reload_client(monkeypatch, mock=True)
    result = c.search("Exa integration", 3)
    for r in result.results:
        assert r.url, "Mock 结果缺少 URL"


def test_api_key_missing_returns_error(monkeypatch):
    """API Key 缺失时 check_config 返回 False（非 Mock 模式）。"""
    c = _reload_client(monkeypatch, mock=False, key="", base_url="https://api.example.com")
    ok, err = c.check_config()
    assert not ok
    assert "KEY" in err or "未设置" in err


def test_http_401_returns_auth_error(monkeypatch):
    """401 → 认证失败错误（非 Mock 模式）。"""
    c = _reload_client(monkeypatch, mock=False, key="fake-key", base_url="https://api.example.com")
    mock_resp = MagicMock()
    mock_resp.status_code = 401
    with patch("services.querit_client._requests.post", return_value=mock_resp):
        result = c.search("test query", 5)
    assert result.success is False
    assert "401" in result.error or "认证" in result.error


def test_http_403_returns_auth_error(monkeypatch):
    """403 → 权限错误（非 Mock 模式）。"""
    c = _reload_client(monkeypatch, mock=False, key="fake-key", base_url="https://api.example.com")
    mock_resp = MagicMock()
    mock_resp.status_code = 403
    with patch("services.querit_client._requests.post", return_value=mock_resp):
        result = c.search("test query", 5)
    assert result.success is False


def test_http_429_returns_rate_limit_error(monkeypatch):
    """429 → 限频错误（非 Mock 模式）。"""
    c = _reload_client(monkeypatch, mock=False, key="fake-key", base_url="https://api.example.com")
    mock_resp = MagicMock()
    mock_resp.status_code = 429
    with patch("services.querit_client._requests.post", return_value=mock_resp):
        result = c.search("test query", 5)
    assert result.success is False
    assert "429" in result.error or "限频" in result.error


def test_timeout_returns_failed(monkeypatch):
    """超时 → failed 且不抛异常（非 Mock 模式）。"""
    import requests as req
    c = _reload_client(monkeypatch, mock=False, key="fake-key",
                       base_url="https://api.example.com", retries=0)
    with patch("services.querit_client._requests.post",
               side_effect=req.exceptions.Timeout()):
        result = c.search("test query", 5)
    assert result.success is False
    assert "超时" in result.error or "Timeout" in result.error


def test_5xx_error_is_recorded(monkeypatch):
    """5xx 服务端错误被记录（非 Mock 模式）。"""
    c = _reload_client(monkeypatch, mock=False, key="fake-key",
                       base_url="https://api.example.com", retries=0)
    mock_resp = MagicMock()
    mock_resp.status_code = 500
    with patch("services.querit_client._requests.post", return_value=mock_resp):
        result = c.search("test query", 5)
    assert result.success is False


def test_single_query_failure_does_not_affect_batch(monkeypatch):
    """单 Query 失败不影响其他 Query（Mock 模式）。"""
    c = _reload_client(monkeypatch, mock=True)
    results = [c.search(f"Latest query_{i} update", 2) for i in range(2)]
    assert all(r.success for r in results)


def test_api_key_not_in_error_message(monkeypatch):
    """错误信息中不包含 API Key 内容（非 Mock 模式）。"""
    import requests as req
    secret_key = "super-secret-key-12345"
    c = _reload_client(monkeypatch, mock=False, key=secret_key,
                       base_url="https://api.example.com", retries=0)
    with patch("services.querit_client._requests.post",
               side_effect=req.exceptions.ConnectionError("refused")):
        result = c.search("test", 5)
    assert secret_key not in result.error


def test_mock_search_returns_results():
    """Mock 模式下 search() 返回成功结果。"""
    from services.querit_client import search
    result = search("Latest Tavily API updates", 5)
    assert result.success is True
    assert result.is_mock is True
    assert len(result.results) > 0


def test_mock_result_has_url():
    """Mock 结果包含 URL。"""
    from services.querit_client import search
    result = search("Exa integration", 3)
    for r in result.results:
        assert r.url, "Mock 结果缺少 URL"


def test_api_key_missing_returns_error(monkeypatch):
    """API Key 缺失时返回明确错误（非 Mock 模式）。"""
    monkeypatch.setenv("QUERIT_MOCK_MODE", "false")
    monkeypatch.setenv("QUERIT_API_KEY", "")
    monkeypatch.setenv("QUERIT_API_BASE_URL", "https://api.example.com")
    import importlib, services.querit_client as c
    importlib.reload(c)
    ok, err = c.check_config()
    assert not ok
    assert "API_KEY" in err or "未设置" in err


def test_http_401_returns_auth_error(monkeypatch):
    """401 → 认证失败错误。"""
    monkeypatch.setenv("QUERIT_MOCK_MODE", "false")
    monkeypatch.setenv("QUERIT_API_KEY", "fake-key")
    monkeypatch.setenv("QUERIT_API_BASE_URL", "https://api.example.com")
    import importlib, services.querit_client as c
    importlib.reload(c)
    mock_resp = MagicMock()
    mock_resp.status_code = 401
    with patch("services.querit_client._requests.post", return_value=mock_resp):
        result = c.search("test query", 5)
    assert result.success is False
    assert "401" in result.error or "认证" in result.error


def test_http_403_returns_auth_error(monkeypatch):
    """403 → 认证或权限错误。"""
    monkeypatch.setenv("QUERIT_MOCK_MODE", "false")
    monkeypatch.setenv("QUERIT_API_KEY", "fake-key")
    monkeypatch.setenv("QUERIT_API_BASE_URL", "https://api.example.com")
    import importlib, services.querit_client as c
    importlib.reload(c)
    mock_resp = MagicMock()
    mock_resp.status_code = 403
    with patch("services.querit_client._requests.post", return_value=mock_resp):
        result = c.search("test query", 5)
    assert result.success is False


def test_http_429_returns_rate_limit_error(monkeypatch):
    """429 → 限频错误。"""
    monkeypatch.setenv("QUERIT_MOCK_MODE", "false")
    monkeypatch.setenv("QUERIT_API_KEY", "fake-key")
    monkeypatch.setenv("QUERIT_API_BASE_URL", "https://api.example.com")
    import importlib, services.querit_client as c
    importlib.reload(c)
    mock_resp = MagicMock()
    mock_resp.status_code = 429
    with patch("services.querit_client._requests.post", return_value=mock_resp):
        result = c.search("test query", 5)
    assert result.success is False
    assert "429" in result.error or "限频" in result.error


def test_timeout_returns_failed(monkeypatch):
    """超时 → failed 且不抛异常。"""
    monkeypatch.setenv("QUERIT_MOCK_MODE", "false")
    monkeypatch.setenv("QUERIT_API_KEY", "fake-key")
    monkeypatch.setenv("QUERIT_API_BASE_URL", "https://api.example.com")
    import importlib, services.querit_client as c, requests as req
    importlib.reload(c)
    with patch("services.querit_client._requests.post", side_effect=req.exceptions.Timeout()):
        result = c.search("test query", 5)
    assert result.success is False
    assert "超时" in result.error or "Timeout" in result.error


def test_5xx_error_is_recorded(monkeypatch):
    """5xx 服务端错误被记录，不崩溃。"""
    monkeypatch.setenv("QUERIT_MOCK_MODE", "false")
    monkeypatch.setenv("QUERIT_API_KEY", "fake-key")
    monkeypatch.setenv("QUERIT_API_BASE_URL", "https://api.example.com")
    monkeypatch.setenv("QUERIT_API_MAX_RETRIES", "0")
    import importlib, services.querit_client as c
    importlib.reload(c)
    mock_resp = MagicMock()
    mock_resp.status_code = 500
    with patch("services.querit_client._requests.post", return_value=mock_resp):
        result = c.search("test query", 5)
    assert result.success is False


def test_single_query_failure_does_not_affect_batch():
    """单 Query 失败不影响调用方批次中的其他 Query。"""
    from services.querit_client import search
    results = []
    for url_key in ["ok_query_1", "ok_query_2"]:
        r = search(f"Latest {url_key} update", 2)
        results.append(r)
    assert all(r.success for r in results)


def test_api_key_not_in_error_message(monkeypatch):
    """错误信息中不包含 API Key 内容。"""
    monkeypatch.setenv("QUERIT_MOCK_MODE", "false")
    monkeypatch.setenv("QUERIT_API_KEY", "super-secret-key-12345")
    monkeypatch.setenv("QUERIT_API_BASE_URL", "https://api.example.com")
    import importlib, services.querit_client as c, requests as req
    importlib.reload(c)
    with patch("services.querit_client._requests.post", side_effect=req.exceptions.ConnectionError("refused")):
        result = c.search("test", 5)
    assert "super-secret-key-12345" not in result.error
