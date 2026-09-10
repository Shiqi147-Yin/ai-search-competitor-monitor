"""test_github_event_aggregator.py
验证 GitHub commit 聚合逻辑。
"""
import pytest
from services.github_monitor import GitHubCommitRecord
from services.github_event_aggregator import (
    aggregate_commits, _is_merge_commit, _keyword_overlap, GitHubAggregatedEvent,
)


def _make_commit(repo, sha, title, date, url=""):
    return GitHubCommitRecord(
        repository=repo,
        commit_sha=sha,
        commit_title=title,
        commit_url=url or f"https://github.com/{repo}/commit/{sha}",
        commit_date=date,
    )


# ── _is_merge_commit ───────────────────────────────────────────

def test_merge_commit_detected():
    assert _is_merge_commit("Merge pull request #123 from feature/x")
    assert _is_merge_commit("Merge branch 'main' into dev")
    assert _is_merge_commit("Merge remote-tracking branch 'origin/main'")


def test_functional_commit_not_detected_as_merge():
    assert not _is_merge_commit("Add streaming support for Research tool")
    assert not _is_merge_commit("Fix timeout handling")
    assert not _is_merge_commit("Update README")


# ── _keyword_overlap ──────────────────────────────────────────

def test_high_overlap_related_commits():
    score = _keyword_overlap("Add streaming support for Research", "Fix streaming timeout in Research")
    assert score >= 0.3, f"Expected high overlap, got {score}"


def test_low_overlap_unrelated_commits():
    score = _keyword_overlap("Update README documentation", "Fix payment processing bug")
    assert score < 0.3, f"Expected low overlap, got {score}"


# ── aggregate_commits ─────────────────────────────────────────

def test_same_topic_commits_aggregated():
    """同主题 commit 应聚合为一个事件。"""
    commits = [
        _make_commit("tavily-ai/tavily-mcp", "abc1", "Add streaming support for Research tool", "2026-07-10"),
        _make_commit("tavily-ai/tavily-mcp", "abc2", "Fix streaming timeout in Research", "2026-07-10"),
    ]
    events = aggregate_commits(commits, time_window_days=3, overlap_threshold=0.3)
    assert len(events) == 1
    assert events[0].commit_count == 2
    assert len(events[0].commit_urls) == 2


def test_different_topic_commits_not_aggregated():
    """不同主题的 commit 不应错误聚合。"""
    commits = [
        _make_commit("tavily-ai/tavily-mcp", "abc1", "Add streaming support for Research", "2026-07-10"),
        _make_commit("tavily-ai/tavily-mcp", "xyz1", "Fix authentication token expiry issue", "2026-07-10"),
    ]
    events = aggregate_commits(commits, time_window_days=3, overlap_threshold=0.3)
    assert len(events) == 2, f"不同主题应各自独立，实际聚合数: {len(events)}"


def test_merge_commits_not_counted():
    """Merge commit 不应进入聚合计数。"""
    commits = [
        _make_commit("tavily-ai/tavily-mcp", "abc1", "Add streaming support", "2026-07-10"),
        _make_commit("tavily-ai/tavily-mcp", "mrg1", "Merge pull request #99 from feature/streaming", "2026-07-10"),
    ]
    events = aggregate_commits(commits)
    # Merge commit 过滤后只剩1条功能 commit
    total_commits = sum(e.commit_count for e in events)
    assert total_commits == 1, f"Merge commit 不应计数，实际: {total_commits}"


def test_all_commit_urls_preserved():
    """聚合后所有原始 commit URL 必须保留。"""
    commits = [
        _make_commit("tavily-ai/tavily-mcp", "abc1", "Add streaming support for Research", "2026-07-10",
                     url="https://github.com/tavily-ai/tavily-mcp/commit/abc1"),
        _make_commit("tavily-ai/tavily-mcp", "abc2", "Fix streaming timeout in Research", "2026-07-10",
                     url="https://github.com/tavily-ai/tavily-mcp/commit/abc2"),
    ]
    events = aggregate_commits(commits)
    all_urls = []
    for e in events:
        all_urls.extend(e.commit_urls)
    assert "https://github.com/tavily-ai/tavily-mcp/commit/abc1" in all_urls
    assert "https://github.com/tavily-ai/tavily-mcp/commit/abc2" in all_urls


def test_commits_too_far_apart_not_aggregated():
    """时间间隔超过 time_window_days 的 commit 不聚合。"""
    commits = [
        _make_commit("tavily-ai/tavily-mcp", "abc1", "Add streaming support for Research", "2026-07-01"),
        _make_commit("tavily-ai/tavily-mcp", "abc2", "Fix streaming timeout in Research", "2026-07-10"),
    ]
    events = aggregate_commits(commits, time_window_days=3, overlap_threshold=0.3)
    assert len(events) == 2, "时间间隔超过阈值不应聚合"


def test_empty_commits_returns_empty():
    assert aggregate_commits([]) == []


def test_all_merge_commits_returns_empty():
    commits = [
        _make_commit("r/r", "m1", "Merge pull request #1 from a/b", "2026-07-10"),
        _make_commit("r/r", "m2", "Merge branch 'main' into dev", "2026-07-10"),
    ]
    events = aggregate_commits(commits)
    assert events == []
