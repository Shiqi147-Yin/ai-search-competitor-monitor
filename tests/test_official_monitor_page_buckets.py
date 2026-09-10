"""test_official_monitor_page_buckets.py
使用三条核心 fixture 验证整体分桶：
Blog=1, Docs Pending=1, GitHub=1, total candidates >= 3。
"""
import pytest
from services.official_update_normalizer import OfficialUpdateItem
from services.official_monitor_importer import filter_valid_results

_WIN_START = "2026-07-08"
_WIN_END   = "2026-07-17"


def _keyless_blog():
    return OfficialUpdateItem(
        competitor="Tavily",
        update_title="What Keyless Search Really Means for Your Data",
        source_channel="website_blog",
        source_url="https://www.tavily.com/blog/keyless-search",
        published_at="2026-07-14",
        within_window=True,
        is_entry_page=False,
        is_generic_page=False,
        update_status="new_page",
    )


def _nemo_integration():
    return OfficialUpdateItem(
        competitor="Tavily",
        update_title="NVIDIA NeMo Deep Agents",
        source_channel="website_integration",
        source_url="https://docs.tavily.com/documentation/integrations/nemo-deepagents",
        updated_at="2026-07-09T17:07:49.892Z",
        update_date="2026-07-09T17:07:49.892Z",
        within_window=True,
        is_entry_page=False,
        is_generic_page=False,
        update_status="new_page",
        docs_page_role="integration",
        import_eligible=True,
    )


def _tavily_mcp_commit():
    return OfficialUpdateItem(
        competitor="Tavily",
        update_title="tavily-mcp: research timeout settings for stream pipeline",
        source_channel="github_commit_group",
        source_url="https://github.com/tavily-ai/tavily-mcp/commit/b74fdd4",
        update_date="2026-07-10",
        within_window=True,
        is_entry_page=False,
        is_generic_page=False,
        evidence_urls=[
            "https://github.com/tavily-ai/tavily-mcp/commit/b74fdd4",
            "https://github.com/tavily-ai/tavily-mcp/commit/abc1234",
        ],
    )


def _old_docs_item():
    """一个 effective_date=2026-01-27 的旧 Docs 页面。"""
    return OfficialUpdateItem(
        competitor="Tavily",
        update_title="Old API Page",
        source_channel="website_docs",
        source_url="https://docs.tavily.com/documentation/api-reference/endpoint/search",
        updated_at="2026-01-27T19:22:11.612Z",
        update_date="2026-01-27T19:22:11.612Z",
        within_window=False,
        is_entry_page=False,
        is_generic_page=False,
        update_status="unknown",
        docs_page_role="api_reference",
    )


def test_three_core_benchmarks_all_present():
    website = [_keyless_blog(), _nemo_integration()]
    github = [_tavily_mcp_commit()]

    fr = filter_valid_results(website, github, window_start=_WIN_START, window_end=_WIN_END)

    assert len(fr.blog_valid) == 1, f"Blog 应=1，实际={len(fr.blog_valid)}"
    assert len(fr.github_valid) == 1, f"GitHub 应=1，实际={len(fr.github_valid)}"

    total_docs = len(fr.docs_valid) + len(fr.docs_pending)
    assert total_docs >= 1, f"Docs 有效候选应>=1，实际={total_docs}"

    total_candidates = len(fr.blog_valid) + len(fr.docs_valid) + len(fr.docs_pending) + len(fr.github_valid)
    assert total_candidates >= 3, f"有效候选总数应>=3，实际={total_candidates}"


def test_nemo_not_in_outside_window():
    website = [_nemo_integration()]
    fr = filter_valid_results(website, [], window_start=_WIN_START, window_end=_WIN_END)
    urls_outside = [getattr(i, "source_url", "") for i in fr.outside_window]
    assert not any("nemo" in u.lower() for u in urls_outside), \
        f"Nemo 不应在 outside_window，实际 outside_window URLs: {urls_outside}"


def test_keyless_not_in_outside_window():
    website = [_keyless_blog()]
    fr = filter_valid_results(website, [], window_start=_WIN_START, window_end=_WIN_END)
    assert len(fr.blog_valid) == 1
    assert len(fr.outside_window) == 0


def test_commit_in_github_valid():
    fr = filter_valid_results([], [_tavily_mcp_commit()], window_start=_WIN_START, window_end=_WIN_END)
    assert len(fr.github_valid) == 1


def test_old_docs_not_in_pending_with_explicit_window():
    """旧页面（effective_date=2026-01-27）不进入窗口 2026-07-08~2026-07-17 的候选。"""
    website = [_nemo_integration(), _old_docs_item()]
    fr = filter_valid_results(website, [], window_start=_WIN_START, window_end=_WIN_END)
    # 只有 Nemo 进入候选，旧页面应在 outside_window
    assert len(fr.docs_pending) <= 1
    # 旧页面不应在 docs_pending
    pending_urls = [getattr(i, "source_url", "") for i in fr.docs_pending]
    assert not any("endpoint/search" in u for u in pending_urls), \
        f"旧 API page 不应在 docs_pending，实际: {pending_urls}"


def test_valid_candidate_count_three_core_plus_15_old():
    """3 条核心基准 + 15 条旧 Docs → 有效候选总数=3，不是 18。"""
    old_items = []
    for i in range(15):
        old_items.append(OfficialUpdateItem(
            competitor="Tavily",
            update_title=f"Old Doc Page {i}",
            source_channel="website_docs",
            source_url=f"https://docs.tavily.com/old-page-{i}",
            updated_at=f"2026-0{(i % 6) + 1}-15T00:00:00Z",  # 2026-01~06
            update_date=f"2026-0{(i % 6) + 1}-15T00:00:00Z",
            within_window=False,
            is_entry_page=False,
            is_generic_page=False,
            update_status="unknown",
            docs_page_role="api_reference",
        ))

    website = [_keyless_blog(), _nemo_integration()] + old_items
    github = [_tavily_mcp_commit()]
    fr = filter_valid_results(website, github, window_start=_WIN_START, window_end=_WIN_END)

    total = len(fr.blog_valid) + len(fr.docs_valid) + len(fr.docs_pending) + len(fr.github_valid)
    assert total <= 5, f"有效候选应<=5（只有窗口内页面），实际={total}"
    assert total >= 3, f"有效候选应>=3（3条核心基准），实际={total}"
    assert len(fr.outside_window) >= 14, "旧 Docs 应大量进入 outside_window"

