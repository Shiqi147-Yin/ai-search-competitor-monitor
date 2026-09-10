"""test_exa_github_relevance.py
验证 GitHub 事件相关性评分器对 Exa 典型 commit 的分类结果。
"""
import pytest
from services.github_relevance_scorer import (
    classify_github_event_relevance,
    filter_events_by_relevance,
    PRIMARY_RESULT_CATEGORIES,
    DIAGNOSTIC_ONLY_CATEGORIES,
)
from services.github_event_aggregator import GitHubAggregatedEvent


def _event(title, key_changes=None, changed_files=None, repo="exa-labs/exa-py"):
    e = GitHubAggregatedEvent(
        event_title=title,
        repository=repo,
        key_changes=key_changes or [title],
        changed_files=changed_files or [],
    )
    return e


# ── 相关性分类 ────────────────────────────────────────────────

def test_crawl_deprecation_is_sdk_api_change():
    result = classify_github_event_relevance(
        event_title="fix: mark start_crawl_date and end_crawl_date as deprecated",
        key_changes=["fix: mark start_crawl_date and end_crawl_date as deprecated"],
        changed_files=["exa/types.py"],
        repository="exa-labs/exa-py",
    )
    assert result.category == "sdk_api_change"
    assert result.should_be_primary_result is True


def test_release_bump_is_primary_product_capability():
    """SDK releases are product_capability — they are worth tracking as competitor updates."""
    result = classify_github_event_relevance(
        event_title="chore(master): release 2.16.1",
        key_changes=["chore(master): release 2.16.1", "Bumps version to 2.16.1"],
        changed_files=["package.json", "CHANGELOG.md"],
        repository="exa-labs/exa-js",
    )
    # SDK release: should be product_capability (trackable) not plain maintenance
    assert result.category in ("product_capability", "maintenance")
    assert result.is_release_or_version_bump is True


def test_ci_lint_is_maintenance():
    result = classify_github_event_relevance(
        event_title="Pin Prettier 3.8.1, reformat TypeScript",
        key_changes=["Pin Prettier 3.8.1, reformat TypeScript and gate CI on format:check"],
        changed_files=[".github/workflows/format.yml", "src/utils.ts"],
        repository="exa-labs/exa-mcp-server",
    )
    assert result.category == "maintenance"
    assert result.should_be_primary_result is False


def test_search_api_feature_is_core():
    result = classify_github_event_relevance(
        event_title="feat: add semantic search with neural embedding support",
        key_changes=["feat: add semantic search with neural embedding support"],
        changed_files=["exa/search.py"],
        repository="exa-labs/exa-py",
    )
    assert result.category == "core_search_api"
    assert result.should_be_primary_result is True


def test_mcp_public_capability_is_integration_ecosystem():
    result = classify_github_event_relevance(
        event_title="Add streaming agent_run tool for MCP plugin",
        key_changes=["Add streaming agent_run tool for MCP plugin", "Expose new connector interface"],
        changed_files=["src/tools/agent.ts", "src/index.ts"],
        repository="exa-labs/exa-mcp-server",
    )
    assert result.should_be_primary_result is True


def test_readme_update_is_developer_experience():
    result = classify_github_event_relevance(
        event_title="Rewrite README for clearer install surfaces",
        key_changes=["Rewrite README for clearer install surfaces"],
        changed_files=["README.md"],
        repository="exa-labs/exa-mcp-server",
    )
    assert result.category == "developer_experience"
    assert result.should_be_primary_result is True


# ── filter_events_by_relevance ────────────────────────────────

def test_filter_separates_primary_and_diagnostic():
    events = [
        _event("feat: add semantic search with neural embedding"),
        _event("chore(master): release 2.16.1"),
        _event("Pin Prettier 3.8.1, reformat TypeScript"),
        _event("fix: mark start_crawl_date as deprecated"),
    ]
    primary, diagnostic = filter_events_by_relevance(events)
    assert len(primary) >= 2
    assert len(diagnostic) >= 1


def test_all_events_classified():
    events = [_event(f"commit {i}") for i in range(5)]
    primary, diagnostic = filter_events_by_relevance(events)
    assert len(primary) + len(diagnostic) == 5
