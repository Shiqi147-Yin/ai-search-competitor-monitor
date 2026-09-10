"""test_streamlit_widget_keys.py
验证同一 item 在不同 section 渲染时生成不同 widget key。
（不依赖 Streamlit 运行时，直接测试 key 生成逻辑）
"""
import hashlib
import pytest


def _stable_id(url: str) -> str:
    return hashlib.md5((url or "").encode()).hexdigest()[:10]


def _widget_key(prefix: str, section_key: str, stable_id: str) -> str:
    return f"{prefix}_{section_key}_{stable_id}"


NEMO_URL = "https://docs.tavily.com/documentation/integrations/nemo-deepagents"
KEYLESS_URL = "https://www.tavily.com/blog/keyless-search"


def test_same_item_different_sections_have_unique_keys():
    """同一 item 在 all / docs / pend 三个 section 生成三个不同 key。"""
    sid = _stable_id(NEMO_URL)
    keys = [
        _widget_key("chk", "all_pend", sid),
        _widget_key("chk", "docs", sid),
        _widget_key("chk", "pend", sid),
    ]
    assert len(set(keys)) == 3, f"期望 3 个唯一 key，实际: {keys}"


def test_different_items_same_section_have_unique_keys():
    """不同 item 在同一 section 生成不同 key。"""
    sid_nemo    = _stable_id(NEMO_URL)
    sid_keyless = _stable_id(KEYLESS_URL)
    key_nemo    = _widget_key("chk", "all", sid_nemo)
    key_keyless = _widget_key("chk", "all", sid_keyless)
    assert key_nemo != key_keyless


def test_same_item_same_section_same_key():
    """同一 item 在同一 section 两次渲染 key 相同（Streamlit 去重要靠 section_key 区分）。"""
    sid  = _stable_id(NEMO_URL)
    key1 = _widget_key("chk", "docs", sid)
    key2 = _widget_key("chk", "docs", sid)
    assert key1 == key2


def test_all_widget_prefixes_unique_across_sections():
    """tab 0 (all) 和 tab 2 (docs) 的所有 widget key 不重叠。"""
    nemo_sid = _stable_id(NEMO_URL)
    all_keys = {
        _widget_key("chk", "all",  nemo_sid),
        _widget_key("sum", "all",  nemo_sid),
        _widget_key("cat", "all",  nemo_sid),
        _widget_key("chk", "docs", nemo_sid),
        _widget_key("sum", "docs", nemo_sid),
        _widget_key("cat", "docs", nemo_sid),
    }
    assert len(all_keys) == 6
