"""测试：环境变量布尔值解析"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from env_loader import get_env_bool
import os


def test_false_string_is_false(monkeypatch):
    monkeypatch.setenv("TEST_BOOL", "false")
    assert get_env_bool("TEST_BOOL") is False


def test_False_string_is_false(monkeypatch):
    monkeypatch.setenv("TEST_BOOL", "False")
    assert get_env_bool("TEST_BOOL") is False


def test_zero_string_is_false(monkeypatch):
    monkeypatch.setenv("TEST_BOOL", "0")
    assert get_env_bool("TEST_BOOL") is False


def test_off_string_is_false(monkeypatch):
    monkeypatch.setenv("TEST_BOOL", "off")
    assert get_env_bool("TEST_BOOL") is False


def test_no_string_is_false(monkeypatch):
    monkeypatch.setenv("TEST_BOOL", "no")
    assert get_env_bool("TEST_BOOL") is False


def test_true_string_is_true(monkeypatch):
    monkeypatch.setenv("TEST_BOOL", "true")
    assert get_env_bool("TEST_BOOL") is True


def test_one_string_is_true(monkeypatch):
    monkeypatch.setenv("TEST_BOOL", "1")
    assert get_env_bool("TEST_BOOL") is True


def test_yes_string_is_true(monkeypatch):
    monkeypatch.setenv("TEST_BOOL", "yes")
    assert get_env_bool("TEST_BOOL") is True


def test_on_string_is_true(monkeypatch):
    monkeypatch.setenv("TEST_BOOL", "on")
    assert get_env_bool("TEST_BOOL") is True


def test_missing_uses_default_false(monkeypatch):
    """变量不存在时使用 default=False。"""
    monkeypatch.delenv("TEST_BOOL_MISSING", raising=False)
    assert get_env_bool("TEST_BOOL_MISSING", default=False) is False


def test_missing_uses_default_true(monkeypatch):
    """变量不存在时使用 default=True。"""
    monkeypatch.delenv("TEST_BOOL_MISSING", raising=False)
    assert get_env_bool("TEST_BOOL_MISSING", default=True) is True


def test_case_insensitive(monkeypatch):
    """大小写不敏感。"""
    for val in ("TRUE", "True", "tRuE", "FALSE", "FaLsE"):
        monkeypatch.setenv("TEST_BOOL", val)
        result = get_env_bool("TEST_BOOL")
        expected = val.lower() in {"true", "1", "yes", "on"}
        assert result == expected, f"值 '{val}' 期望 {expected} 但得到 {result}"


def test_whitespace_stripped(monkeypatch):
    """前后空格被忽略。"""
    monkeypatch.setenv("TEST_BOOL", "  false  ")
    assert get_env_bool("TEST_BOOL") is False
    monkeypatch.setenv("TEST_BOOL", " true ")
    assert get_env_bool("TEST_BOOL") is True
