"""test_raw_records_not_counted_as_candidates.py
验证：原始 raw commit 不计入有效候选总数，只有聚合后的 final events 计入。
"""
import pytest
from services.github_monitor import GitHubCommitRecord
from services.github_event_aggregator import aggregate_commits
from services.github_relevance_scorer import filter_events_by_relevance


def _commit(title, date="2026-08-07", repo="exa-labs/exa-py"):
    return GitHubCommitRecord(
        repository=repo, commit_sha="abc", commit_title=title,
        commit_url=f"https://github.com/{repo}/commit/abc",
        commit_date=date,
    )


def test_raw_records_vs_aggregated_events():
    """Relevance filter should reduce primary events below raw commit count."""
    raw = [
        _commit("chore(master): release 2.17.0 (#242)"),
        _commit("feat(agent): add max effort and budgets (#240)"),
        _commit("chore(master): release 2.16.2 (#238)"),
        _commit("fix: update Category values and accept str at runtime (#237)", date="2026-07-27"),
        _commit("Update Category values and accept str at runtime (#236)", date="2026-07-27"),
        _commit("Rewrite README for clearer install surfaces (#409)", repo="exa-labs/exa-mcp-server"),
        _commit("Add Agent Plugins package metadata (#408)", repo="exa-labs/exa-mcp-server"),
        _commit("Drop unused docs, Docker, and whoami. (#411)", repo="exa-labs/exa-mcp-server"),
        _commit("Add npm publish workflow (#404)", repo="exa-labs/exa-mcp-server", date="2026-08-01"),
        _commit("Bump version to 3.4.0 (#403)", repo="exa-labs/exa-mcp-server", date="2026-08-01"),
        _commit("Pin Prettier 3.8.1 (#402)", repo="exa-labs/exa-mcp-server", date="2026-08-01"),
        _commit("Make agent_run resumable (#401)", repo="exa-labs/exa-mcp-server", date="2026-08-01"),
        _commit("fix: pin publish workflow to npm@11", date="2026-07-27"),
    ]
    assert len(raw) == 13

    events = aggregate_commits(raw)
    primary, diagnostic = filter_events_by_relevance(events)

    # primary + diagnostic = total events (no raw commits double-counted)
    assert len(primary) + len(diagnostic) == len(events)

    # At least some commits go to diagnostic (not all are primary)
    assert len(diagnostic) > 0, "Some low-value commits should be filtered to diagnostic"

    # primary count must be < raw count (relevance filter is doing work)
    assert len(primary) < len(raw), \
        f"Primary events should be < raw commits: primary={len(primary)} raw={len(raw)}"


def test_valid_candidate_count_uses_final_events():
    """有效候选总数只统计最终事件，不含原始 commit 数量。"""
    raw = [_commit(f"commit {i}") for i in range(5)]
    events = aggregate_commits(raw)
    primary, _ = filter_events_by_relevance(events)
    # Candidate count should be the number of primary events
    assert len(primary) <= len(raw)
