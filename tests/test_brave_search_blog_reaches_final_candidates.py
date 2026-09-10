"""test_brave_search_blog_reaches_final_candidates.py
验证 Brave Search Blog 文章（Search-related + in-window）能到达 final candidates。
"""
import pytest
from dataclasses import dataclass, field
from services.official_monitor_importer import filter_valid_results


@dataclass
class _MockBlogItem:
    source_channel: str = "website_blog"
    source_url: str = ""
    update_title: str = ""
    update_status: str = "new_page"
    published_at: str = ""
    updated_at: str = ""
    update_date: str = ""
    within_window: object = False
    is_generic_page: bool = False
    is_entry_page: bool = False
    docs_page_role: str = "detail_article"
    import_eligible: bool = True
    brave_search_relevance: bool = True
    brave_search_score: float = 0.7
    brave_search_reason: str = "Search keywords: ['search api']"


def test_brave_search_blog_reaches_final_candidates():
    """Brave Place Search API 文章（Search-related, in-window）必须进入 fr.blog_valid。"""
    place_search_item = _MockBlogItem(
        update_title="Brave Place Search API: The Google Maps Alternative That Costs 6-7x Less",
        source_url="https://brave.com/blog/place-search-improved/",
        published_at="2026-07-08T00:00:00Z",
        update_date="2026-07-08T00:00:00Z",
        within_window=True,   # 在 2026-07-01 ~ 2026-07-15 窗口内
        brave_search_relevance=True,
        brave_search_score=0.7,
    )
    outside_item = _MockBlogItem(
        update_title="Brave Search API launches independent index",
        source_url="https://brave.com/blog/brave-search-launch/",
        published_at="2022-06-22T00:00:00Z",
        within_window=False,
    )

    fr = filter_valid_results(
        website_items=[place_search_item, outside_item],
        github_items=[],
        window_start="2026-07-01",
        window_end="2026-07-15",
    )

    assert len(fr.blog_valid) == 1, (
        f"Expected 1 blog_valid, got {len(fr.blog_valid)}"
    )
    assert fr.blog_valid[0].source_url == "https://brave.com/blog/place-search-improved/", (
        f"Wrong item in blog_valid: {fr.blog_valid[0].source_url}"
    )
    assert len(fr.outside_window) == 1
    assert fr.outside_window[0].source_url == "https://brave.com/blog/brave-search-launch/"


def test_search_related_in_window_always_included():
    """无论 Docs=0 / GitHub=0 / benchmark 是否定义，in-window blog 必须出现在最终候选。"""
    items = [
        _MockBlogItem(
            update_title="Brave Search API New Feature",
            source_url="https://brave.com/blog/new-search-feature/",
            published_at="2026-07-10T00:00:00Z",
            within_window=True,
        )
    ]

    fr = filter_valid_results(
        website_items=items,
        github_items=[],
        window_start="2026-07-01",
        window_end="2026-07-15",
    )

    assert len(fr.blog_valid) == 1
    total_candidates = fr.blog_valid + fr.docs_valid + fr.github_valid + fr.docs_pending
    assert len(total_candidates) == 1, (
        "in-window blog should be in final candidates regardless of other sources being 0"
    )
