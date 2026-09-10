"""test_first_seen_does_not_override_source_date.py
验证 first_seen_at 不会让旧页面进入当前时间窗口候选。
"""
import pytest
from services.official_update_normalizer import OfficialUpdateItem
from services.official_monitor_importer import filter_valid_results


def _old_docs_item(update_status="unknown"):
    """一个 2026-01-27 更新的 Docs 页面，系统在 2026-08-10 首次发现。"""
    return OfficialUpdateItem(
        competitor="Tavily",
        update_title="Old API Reference Page",
        source_channel="website_docs",
        source_url="https://docs.tavily.com/documentation/api-reference/endpoint/search",
        published_at="",
        updated_at="2026-01-27T19:22:11.612Z",   # 真实页面日期：窗口外
        update_date="2026-01-27T19:22:11.612Z",
        within_window=False,
        is_entry_page=False,
        is_generic_page=False,
        update_status=update_status,
        docs_page_role="api_reference",
        import_eligible=True,
    )


def test_old_page_with_unknown_status_not_in_pending():
    """页面 effective_date=2026-01-27，窗口 2026-07-08~2026-07-17 → 不进入 docs_pending。"""
    item = _old_docs_item(update_status="unknown")
    fr = filter_valid_results(
        [item], [],
        window_start="2026-07-08",
        window_end="2026-07-17",
    )
    assert len(fr.docs_pending) == 0, \
        f"旧页面不应进入 docs_pending，实际 docs_pending={len(fr.docs_pending)}"
    assert len(fr.outside_window) >= 1


def test_old_page_with_first_seen_not_in_pending():
    """页面 effective_date=2026-01-27，update_status=first_seen → 不进入 docs_pending。"""
    item = _old_docs_item(update_status="first_seen")
    fr = filter_valid_results(
        [item], [],
        window_start="2026-07-08",
        window_end="2026-07-17",
    )
    assert len(fr.docs_pending) == 0
    assert len(fr.outside_window) >= 1


def test_old_page_within_window_false_effective_date_outside():
    """within_window=False 且 effective_date 在窗口外 → 进入 outside_window。"""
    item = _old_docs_item(update_status="new_page")
    fr = filter_valid_results(
        [item], [],
        window_start="2026-07-08",
        window_end="2026-07-17",
    )
    assert len(fr.docs_valid) == 0
    assert len(fr.docs_pending) == 0
    assert len(fr.outside_window) >= 1
