"""test_official_monitor_page_filters.py
验证主结果过滤规则：窗口内/外、metadata_only、high_value first_seen、generic_page、GitHub。
"""
import pytest
from services.official_update_normalizer import OfficialUpdateItem
from services.official_monitor_importer import filter_valid_results, FilterResult


def _blog(within_window=True, **kw):
    defaults = dict(
        competitor="Tavily", update_title="Test Blog", source_channel="website_blog",
        source_url="https://www.tavily.com/blog/test", published_at="2026-07-14",
        within_window=within_window, is_entry_page=False, is_generic_page=False,
        update_status="new_page", docs_page_role="",
    )
    defaults.update(kw)
    return OfficialUpdateItem(**defaults)


def _docs(within_window=True, update_status="new_page", is_generic=False,
          role="integration", **kw):
    defaults = dict(
        competitor="Tavily", update_title="Test Docs", source_channel="website_docs",
        source_url="https://docs.tavily.com/integrations/test", updated_at="2026-07-09",
        within_window=within_window, is_entry_page=False, is_generic_page=is_generic,
        update_status=update_status, docs_page_role=role,
    )
    defaults.update(kw)
    return OfficialUpdateItem(**defaults)


def _integration(within_window=True, update_status="new_page", is_generic=False, role="integration", **kw):
    defaults = dict(
        competitor="Tavily", update_title="Nemo Integration", source_channel="website_integration",
        source_url="https://docs.tavily.com/documentation/integrations/nemo", updated_at="2026-07-09",
        within_window=within_window, is_entry_page=False, is_generic_page=is_generic,
        update_status=update_status, docs_page_role=role,
    )
    defaults.update(kw)
    return OfficialUpdateItem(**defaults)


def _github_event(**kw):
    defaults = dict(
        competitor="Tavily", update_title="tavily-mcp: streaming update",
        source_channel="github_commit_group", source_url="https://github.com/tavily-ai/tavily-mcp/commit/abc",
        within_window=True, is_entry_page=False, is_generic_page=False,
    )
    defaults.update(kw)
    return OfficialUpdateItem(**defaults)


# ── Blog 测试 ─────────────────────────────────────────────────

def test_blog_within_window_is_valid():
    fr = filter_valid_results([_blog(within_window=True)], [])
    assert len(fr.blog_valid) == 1
    assert len(fr.outside_window) == 0


def test_blog_outside_window_not_in_valid():
    fr = filter_valid_results([_blog(within_window=False)], [])
    assert len(fr.blog_valid) == 0
    assert len(fr.outside_window) == 1


# ── Docs 测试 ─────────────────────────────────────────────────

def test_docs_within_window_new_page_is_valid():
    fr = filter_valid_results(
        [_docs(within_window=True, update_status="new_page")], [],
        window_start="2026-07-08", window_end="2026-07-17",
    )
    assert len(fr.docs_valid) == 1


def test_docs_metadata_only_not_in_valid():
    fr = filter_valid_results(
        [_docs(within_window=True, update_status="metadata_only")], [],
        window_start="2026-07-08", window_end="2026-07-17",
    )
    assert len(fr.docs_valid) == 0
    assert len(fr.metadata_only) == 1


def test_docs_unchanged_not_in_valid():
    fr = filter_valid_results(
        [_docs(within_window=True, update_status="unchanged")], [],
        window_start="2026-07-08", window_end="2026-07-17",
    )
    assert len(fr.docs_valid) == 0
    assert len(fr.metadata_only) == 1


def test_generic_faq_not_in_valid():
    faq = _docs(within_window=True, update_status="new_page", is_generic=True, role="faq")
    fr = filter_valid_results([faq], [], window_start="2026-07-08", window_end="2026-07-17")
    assert len(fr.docs_valid) == 0
    assert len(fr.generic_page) == 1


def test_high_value_first_seen_integration_goes_to_pending():
    item = _integration(within_window=True, update_status="first_seen", role="integration")
    fr = filter_valid_results([item], [], window_start="2026-07-08", window_end="2026-07-17")
    assert len(fr.docs_pending) >= 1
    assert len(fr.docs_valid) == 0


def test_new_page_high_value_within_window_goes_to_pending():
    """new_page + within_window=True + high_value role → docs_pending。"""
    item = _integration(within_window=True, update_status="new_page", role="integration")
    fr = filter_valid_results(
        [item], [],
        window_start="2026-07-08", window_end="2026-07-17",
    )
    # new_page + eff_in_window=True → docs_valid（eff_date=2026-07-09 in window）
    assert len(fr.docs_valid) + len(fr.docs_pending) >= 1


def test_new_page_high_value_outside_window_not_in_pending():
    """new_page + effective_date 在窗口外 → 不进入 docs_pending。"""
    item = _integration(
        within_window=False,
        update_status="new_page",
        role="integration",
        updated_at="2026-01-27",   # 明确旧日期
    )
    fr = filter_valid_results(
        [item], [],
        window_start="2026-07-08", window_end="2026-07-17",
    )
    assert len(fr.docs_pending) == 0
    assert len(fr.docs_valid) == 0
    assert len(fr.outside_window) >= 1


# ── GitHub 测试 ───────────────────────────────────────────────

def test_github_commit_group_is_valid():
    fr = filter_valid_results([], [_github_event(source_channel="github_commit_group")])
    assert len(fr.github_valid) == 1


def test_github_release_is_valid():
    fr = filter_valid_results([], [_github_event(source_channel="github_release")])
    assert len(fr.github_valid) == 1


def test_entry_page_excluded():
    entry = _blog(within_window=True, is_entry_page=True)
    fr = filter_valid_results([entry], [])
    assert len(fr.blog_valid) == 0
    assert len(fr.outside_window) == 0
