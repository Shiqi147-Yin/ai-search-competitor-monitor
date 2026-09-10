"""test_official_update_normalizer.py
验证各来源归一化为 OfficialUpdateItem 时，关键字段赋值正确，published_at/updated_at 不混用。
"""
import pytest
from services.website_monitor import WebsiteUpdateItem
from services.github_monitor import GitHubReleaseRecord
from services.github_event_aggregator import GitHubAggregatedEvent
from services.official_update_normalizer import (
    normalize_blog_item, normalize_docs_item,
    normalize_github_event, normalize_github_release,
    normalize_all,
)


def _blog_item(**kw):
    defaults = dict(
        competitor="Tavily", source_type="blog",
        source_url="https://www.tavily.com/blog/keyless-search",
        title="What Keyless Search Really Means",
        published_at="2026-07-14", updated_at="",
        page_role="detail_article", is_generic_page=False,
        is_entry_page=False, update_status="new_page",
        discovery_method="official_blog_monitor",
        import_eligible=True, within_window=True,
    )
    defaults.update(kw)
    return WebsiteUpdateItem(**defaults)


def _docs_item(**kw):
    defaults = dict(
        competitor="Tavily", source_type="docs",
        source_url="https://docs.tavily.com/integrations/nemo",
        title="NVIDIA NeMo Deep Agents",
        published_at="", updated_at="2026-07-09",
        page_role="integration", is_generic_page=False,
        is_entry_page=False, update_status="new_page",
        discovery_method="official_docs_monitor",
        import_eligible=True, within_window=True,
    )
    defaults.update(kw)
    return WebsiteUpdateItem(**defaults)


def test_blog_normalization_published_at_set():
    item = normalize_blog_item(_blog_item(), competitor="Tavily")
    assert item.published_at == "2026-07-14"
    assert item.updated_at == ""          # Blog 不填 updated_at
    assert item.source_channel == "website_blog"
    assert item.content_type == "article"
    assert item.update_date == "2026-07-14"


def test_docs_normalization_updated_at_set():
    item = normalize_docs_item(_docs_item(), competitor="Tavily")
    assert item.updated_at == "2026-07-09"
    assert item.published_at == ""        # Docs 严格不填 published_at
    assert item.source_channel == "website_docs"
    assert item.content_type == "docs_update"
    assert item.update_date == "2026-07-09"


def test_integration_channel():
    docs = _docs_item(source_type="integration")
    item = normalize_docs_item(docs, competitor="Tavily")
    assert item.source_channel == "website_integration"


def test_github_event_normalization():
    event = GitHubAggregatedEvent(
        event_title="tavily-mcp: streaming / timeout 相关更新",
        repository="tavily-ai/tavily-mcp",
        start_date="2026-07-10",
        end_date="2026-07-10",
        commit_count=2,
        commit_urls=[
            "https://github.com/tavily-ai/tavily-mcp/commit/abc1",
            "https://github.com/tavily-ai/tavily-mcp/commit/abc2",
        ],
        summary="streaming support; timeout fix",
        key_changes=["Add streaming support", "Fix timeout"],
        category="feature",
        importance="medium",
    )
    item = normalize_github_event(event, competitor="Tavily")
    assert item.source_channel == "github_commit_group"
    assert item.content_type == "commit_group"
    assert item.published_at == ""         # commit group 不填 published_at
    assert item.updated_at == ""           # commit group 不填 updated_at
    assert item.update_date == "2026-07-10"
    assert len(item.evidence_urls) == 2


def test_github_release_normalization():
    release = GitHubReleaseRecord(
        repository="tavily-ai/tavily-mcp",
        version="v0.5.0",
        release_title="v0.5.0 Release",
        release_url="https://github.com/tavily-ai/tavily-mcp/releases/tag/v0.5.0",
        published_at="2026-07-12",
        release_notes="Added streaming support.",
    )
    item = normalize_github_release(release, competitor="Tavily")
    assert item.source_channel == "github_release"
    assert item.content_type == "release"
    assert item.published_at == "2026-07-12"
    assert item.update_date == "2026-07-12"


def test_normalize_all_no_field_mixing():
    """批量归一化后，所有 Blog 的 updated_at 为空，所有 Docs 的 published_at 为空。"""
    blog = _blog_item()
    docs = _docs_item()
    items = normalize_all(
        competitor="Tavily",
        blog_items=[blog],
        docs_items=[docs],
    )
    blog_items = [i for i in items if i.source_channel == "website_blog"]
    docs_items = [i for i in items if i.source_channel == "website_docs"]

    for b in blog_items:
        assert b.updated_at == "", f"Blog updated_at 应为空，实际: {b.updated_at}"
    for d in docs_items:
        assert d.published_at == "", f"Docs published_at 应为空，实际: {d.published_at}"
