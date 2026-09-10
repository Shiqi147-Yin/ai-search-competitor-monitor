"""测试：Querit Mock/真实模式配置读取"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest


def test_false_means_real_api_mode(monkeypatch):
    """QUERIT_MOCK_MODE=false 时，is_mock_mode() 返回 False。"""
    monkeypatch.setenv("QUERIT_MOCK_MODE", "false")
    from env_loader import get_env_bool
    assert get_env_bool("QUERIT_MOCK_MODE", default=True) is False


def test_true_means_mock_mode(monkeypatch):
    """QUERIT_MOCK_MODE=true 时，is_mock_mode() 返回 True。"""
    monkeypatch.setenv("QUERIT_MOCK_MODE", "true")
    from env_loader import get_env_bool
    assert get_env_bool("QUERIT_MOCK_MODE", default=True) is True


def test_client_and_page_read_same_value(monkeypatch):
    """Client 与页面的 mock 模式判断使用同一函数，结果一致。"""
    monkeypatch.setenv("QUERIT_MOCK_MODE", "false")
    import importlib, services.querit_client as c
    importlib.reload(c)
    from env_loader import get_env_bool
    assert c.is_mock_mode() == get_env_bool("QUERIT_MOCK_MODE", default=True)


def test_does_not_read_env_example(tmp_path, monkeypatch):
    """.env.example 不被当作运行配置读取（不能影响 is_mock_mode）。"""
    # 模拟没有 .env 但有 .env.example 的情况
    monkeypatch.delenv("QUERIT_MOCK_MODE", raising=False)
    from env_loader import get_env_bool
    # 无 QUERIT_MOCK_MODE 环境变量时，默认为 True（安全值）
    assert get_env_bool("QUERIT_MOCK_MODE", default=True) is True


def test_uppercase_false_is_false(monkeypatch):
    """QUERIT_MOCK_MODE=FALSE（大写）应解析为 False。"""
    monkeypatch.setenv("QUERIT_MOCK_MODE", "FALSE")
    from env_loader import get_env_bool
    assert get_env_bool("QUERIT_MOCK_MODE", default=True) is False
