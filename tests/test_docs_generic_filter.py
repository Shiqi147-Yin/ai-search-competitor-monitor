"""test_docs_generic_filter.py
验证 FAQ / Welcome 等 generic_page 即使 updated_at 在窗口内也不进入主结果。
"""
import pytest
from services.official_update_normalizer import OfficialUpdateItem
from services.official_monitor_importer import filter_valid_results


def _generic_item(role="faq", within_window=True, status="new_page"):
    return OfficialUpdateItem(
        competitor="Tavily",
        update_title="Frequently Asked Questions",
        source_channel="website_docs",
        source_url="https://docs.tavily.com/faq",
        updated_at="2026-07-10",
        within_window=within_window,
        is_entry_page=False,
        is_generic_page=True,
        update_status=status,
        docs_page_role=role,
        import_eligible=False,
    )


def test_faq_within_window_goes_to_generic_page():
    fr = filter_valid_results(
        [_generic_item(role="faq", within_window=True)], [],
        window_start="2026-07-08", window_end="2026-07-17",
    )
    assert len(fr.generic_page) == 1
    assert len(fr.docs_valid) == 0
    assert len(fr.docs_pending) == 0


def test_welcome_within_window_goes_to_generic_page():
    fr = filter_valid_results(
        [_generic_item(role="welcome", within_window=True)], [],
        window_start="2026-07-08", window_end="2026-07-17",
    )
    assert len(fr.generic_page) == 1
    assert len(fr.docs_valid) == 0
    assert len(fr.docs_pending) == 0


def test_navigation_within_window_goes_to_generic_page():
    fr = filter_valid_results(
        [_generic_item(role="navigation", within_window=True)], [],
        window_start="2026-07-08", window_end="2026-07-17",
    )
    assert len(fr.generic_page) == 1


def test_generic_page_not_in_docs_valid_or_pending():
    items = [
        _generic_item(role="faq"),
        _generic_item(role="welcome"),
        _generic_item(role="generic"),
    ]
    fr = filter_valid_results(items, [], window_start="2026-07-08", window_end="2026-07-17")
    assert len(fr.docs_valid) == 0
    assert len(fr.docs_pending) == 0
    assert len(fr.generic_page) == 3
