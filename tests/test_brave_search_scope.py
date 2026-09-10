"""test_brave_search_scope.py
验证 Brave Search 相关性过滤器对 Blog / Docs / GitHub 的分类正确性。
"""
import pytest
from services.brave_search_relevance import (
    classify_brave_search_relevance,
    filter_brave_items_by_search_relevance,
)


# ── Blog search scope ─────────────────────────────────────────

def test_search_api_blog_is_kept():
    result = classify_brave_search_relevance(
        title="Brave Search API improves Place Search endpoint",
        url="https://brave.com/blog/place-search-improved/",
        summary="Brave's improved Place Search API matches Google Maps on quality.",
    )
    assert result.is_search_related is True, f"reason={result.search_relevance_reason}"


def test_browser_blog_is_filtered():
    result = classify_brave_search_relevance(
        title="BAT Roadmap 4.0 evolves the Basic Attention Token",
        url="https://brave.com/blog/bat-roadmap-4-0/",
        summary="Brave Rewards and Basic Attention Token roadmap for 2026.",
    )
    assert result.is_search_related is False, f"reason={result.search_relevance_reason}"
    assert result.brave_product_area in ("wallet", "rewards", "browser", "other")


def test_browser_container_blog_is_filtered():
    result = classify_brave_search_relevance(
        title="Brave's latest browser offers Containers for better workflow",
        url="https://brave.com/blog/containers/",
        summary="Brave browser v1.92 adds built-in Containers for privacy.",
    )
    assert result.is_search_related is False


def test_search_news_category_url_is_search():
    result = classify_brave_search_relevance(
        title="Brave Search API approaches 700000 OpenClaw users",
        url="https://brave.com/category/brave-search-news/search-api-growth",
    )
    assert result.is_search_related is True


def test_llm_context_api_blog_is_search():
    result = classify_brave_search_relevance(
        title="Brave launches LLM Context API for AI grounding",
        url="https://brave.com/blog/most-powerful-search-api-for-ai/",
        summary="Brave's LLM Context API returns pre-extracted content for LLM consumption.",
    )
    assert result.is_search_related is True


# ── Docs search scope ─────────────────────────────────────────

def test_search_api_docs_page_is_kept():
    result = classify_brave_search_relevance(
        title="Web Search API Parameters",
        url="https://api.search.brave.com/app/documentation/web-search",
    )
    assert result.is_search_related is True


def test_browser_docs_page_is_filtered():
    result = classify_brave_search_relevance(
        title="Brave Browser Group Policy documentation",
        url="https://support.brave.app/hc/en-us/articles/360039248271-Group-Policy",
    )
    assert result.is_search_related is False


# ── GitHub search scope ───────────────────────────────────────

def test_search_skills_commit_is_kept():
    result = classify_brave_search_relevance(
        title="Add SKILL.md for bx (Brave Search CLI)",
        url="https://github.com/brave/brave-search-skills/commit/abc123",
        summary="Documents bx skill for Brave Search API CLI usage.",
    )
    assert result.is_search_related is True


def test_browser_commit_is_filtered():
    result = classify_brave_search_relevance(
        title="Update Brave browser Android release notes",
        url="https://github.com/brave/brave-browser/commit/def456",
        summary="Brave for Android v1.89 brings Shred feature.",
    )
    assert result.is_search_related is False


# ── filter_brave_items_by_search_relevance integration ────────

class _MockItem:
    def __init__(self, title, url, summary=""):
        self.update_title = title
        self.source_url = url
        self.summary = summary


def test_filter_separates_search_and_non_search():
    items = [
        _MockItem("Brave Search API Place Search", "https://brave.com/blog/place-search-improved/"),
        _MockItem("BAT Roadmap 4.0", "https://brave.com/blog/bat-roadmap-4-0/"),
        _MockItem("Brave Browser Containers", "https://brave.com/blog/containers/"),
        _MockItem("LLM Context API launch", "https://brave.com/blog/most-powerful-search-api-for-ai/"),
    ]
    search_related, filtered_out, stats = filter_brave_items_by_search_relevance(items)
    assert len(search_related) >= 2, f"Expected ≥2 search items, got {len(search_related)}"
    assert len(filtered_out) >= 1, f"Expected ≥1 filtered, got {len(filtered_out)}"
    assert stats["scanned"] == 4
    assert stats["search_related"] == len(search_related)
    assert stats["filtered_non_search"] == len(filtered_out)


def test_zero_results_is_valid():
    """0 search-related results is a valid outcome (Brave Search may have no updates)."""
    items = [
        _MockItem("Brave Browser v1.89 Android", "https://brave.com/blog/android-release/"),
        _MockItem("Brave Wallet supports NEAR Intents", "https://brave.com/blog/near-intents/"),
    ]
    search_related, filtered_out, stats = filter_brave_items_by_search_relevance(items)
    assert len(search_related) == 0
    assert stats["search_related"] == 0
    assert stats["scanned"] == 2
