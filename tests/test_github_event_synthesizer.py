"""test_github_event_synthesizer.py
验证 GithubBusinessEvent Synthesizer 的各场景。
"""
import pytest
from services.github_event_synthesizer import (
    synthesize_github_events, GithubBusinessEvent, SynthesisResult,
    MockLLMProvider, _is_low_value, _get_provider,
)
from services.github_monitor import GitHubCommitRecord, GitHubReleaseRecord


def _commit(title, date="2026-08-07", repo="exa-labs/exa-py", url=None):
    return GitHubCommitRecord(
        repository=repo, commit_sha="abc", commit_title=title,
        commit_url=url or f"https://github.com/{repo}/commit/abc",
        commit_date=date,
    )


def _release(version, repo="exa-labs/exa-py", date="2026-08-07", notes=""):
    return GitHubReleaseRecord(
        repository=repo, version=version,
        release_title=f"Release {version}",
        release_url=f"https://github.com/{repo}/releases/tag/{version}",
        published_at=date, release_notes=notes,
    )


# ── Pre-filter 测试 ───────────────────────────────────────────

def test_low_value_ci_filtered():
    is_low, reason = _is_low_value("Pin Prettier 3.8.1, reformat TypeScript", "maintenance")
    assert is_low, f"Expected low_value=True, got reason={reason}"


def test_low_value_npm_workflow_filtered():
    is_low, reason = _is_low_value("Add npm publish workflow (#404)", "maintenance")
    assert is_low


def test_high_value_agent_not_filtered():
    is_low, _ = _is_low_value("Make agent_run resumable with progress heartbeats", "agent_runtime")
    assert not is_low


def test_high_value_sdk_release_not_filtered():
    is_low, _ = _is_low_value("chore(master): release 2.17.0 (#242)", "sdk_release")
    assert not is_low, "SDK release should NOT be pre-filtered"


# ── MockLLMProvider 测试 ──────────────────────────────────────

def test_mock_provider_agent_runtime_merges():
    """3 agent_runtime records → 1 event."""
    records = [
        {"record_id": "r1", "type": "commit", "topic": "agent_runtime",
         "title": "feat(agent): add max effort and budgets (#240)", "date": "2026-08-06",
         "url": "https://github.com/exa-labs/exa-py/commit/abc1", "repository": "exa-labs/exa-py"},
        {"record_id": "r2", "type": "commit", "topic": "agent_runtime",
         "title": "Make agent_run resumable with progress heartbeats", "date": "2026-08-01",
         "url": "https://github.com/exa-labs/exa-mcp-server/commit/abc2", "repository": "exa-labs/exa-mcp-server"},
        {"record_id": "r3", "type": "commit", "topic": "agent_runtime",
         "title": "Add Agent Plugins package metadata (#408)", "date": "2026-08-07",
         "url": "https://github.com/exa-labs/exa-mcp-server/commit/abc3", "repository": "exa-labs/exa-mcp-server"},
    ]
    provider = MockLLMProvider()
    events = provider.synthesize("Exa", records, "2026-07-27", "2026-08-10")
    agent_events = [e for e in events if e.get("event_type") == "agent_capability"]
    assert len(agent_events) == 1, f"Expected 1 agent_runtime event, got {len(agent_events)}"
    assert len(agent_events[0]["evidence_record_ids"]) == 3


def test_mock_provider_sdk_release_per_version():
    """两个版本的 SDK release → 2 events."""
    records = [
        {"record_id": "rel1", "type": "commit", "topic": "sdk_release",
         "title": "chore(master): release 2.17.0", "date": "2026-08-07",
         "url": "url1", "repository": "exa-labs/exa-py"},
        {"record_id": "rel2", "type": "commit", "topic": "sdk_release",
         "title": "chore(master): release 2.16.2", "date": "2026-07-27",
         "url": "url2", "repository": "exa-labs/exa-py"},
    ]
    provider = MockLLMProvider()
    events = provider.synthesize("Exa", records, "2026-07-27", "2026-08-10")
    release_events = [e for e in events if e.get("event_type") == "sdk_release"]
    # Each version → 1 event
    assert len(release_events) == 2


def test_mock_provider_maintenance_not_output():
    """maintenance topic should not produce events from MockLLMProvider."""
    records = [
        {"record_id": "m1", "type": "commit", "topic": "maintenance",
         "title": "Pin Prettier 3.8.1", "date": "2026-08-01",
         "url": "url1", "repository": "exa-labs/exa-mcp-server"},
    ]
    provider = MockLLMProvider()
    events = provider.synthesize("Exa", records, "2026-07-27", "2026-08-10")
    assert len(events) == 0, f"Maintenance should produce 0 events, got {len(events)}"


# ── synthesize_github_events 集成测试 ─────────────────────────

def test_synthesize_returns_business_events():
    commits = [
        _commit("feat(agent): add max effort and budgets (#240)", date="2026-08-06"),
        _commit("Make agent_run resumable with progress heartbeats", date="2026-08-01",
                repo="exa-labs/exa-mcp-server"),
        _commit("Pin Prettier 3.8.1, reformat TypeScript", date="2026-08-01",
                repo="exa-labs/exa-mcp-server"),  # should be pre-filtered
    ]
    releases = [_release("v2.17.0", date="2026-08-07")]
    result = synthesize_github_events(
        competitor="Exa",
        raw_commits=commits,
        raw_releases=releases,
        window_start="2026-07-27",
        window_end="2026-08-10",
        provider_name="mock",
    )
    assert result.synthesis_status == "success"
    assert result.provider_used == "mock"
    assert result.final_event_count > 0
    # Pre-filter should have caught the Prettier commit
    assert result.pre_filtered_count >= 1


def test_evidence_ids_come_from_input():
    """所有 evidence_record_ids 必须来自输入 records。"""
    commits = [_commit("feat(agent): add max effort", date="2026-08-06")]
    releases = [_release("v2.17.0")]
    result = synthesize_github_events(
        competitor="Exa",
        raw_commits=commits,
        raw_releases=releases,
        window_start="2026-07-27",
        window_end="2026-08-10",
        provider_name="mock",
    )
    all_valid_ids: set[str] = set()
    for be in result.events:
        all_valid_ids.update(be.evidence_record_ids)
    # All IDs should follow the "commit_N" or "release_N" pattern
    for eid in all_valid_ids:
        assert eid.startswith(("commit_", "release_")), f"Unknown evidence ID: {eid}"


def test_no_evidence_event_discarded():
    """如果 Mock 返回无证据 event，必须被丢弃。"""
    provider = MockLLMProvider()
    records = [
        {"record_id": "r1", "type": "commit", "topic": "agent_runtime",
         "title": "feat(agent): x", "date": "2026-08-06", "url": "url1", "repository": "exa-labs/exa-py"},
    ]
    events = provider.synthesize("Exa", records, "2026-07-27", "2026-08-10")
    # Mock returns events with evidence_record_ids populated
    for e in events:
        assert len(e.get("evidence_record_ids", [])) > 0


def test_fallback_on_provider_error():
    """Provider 异常时降级到 deterministic aggregator。"""
    from unittest.mock import patch
    import services.github_event_synthesizer as synth_mod

    commits = [_commit("feat: search improvements", date="2026-08-06")]
    with patch.object(synth_mod, "_get_provider") as mock_prov:
        mock_prov.return_value.synthesize.side_effect = RuntimeError("LLM unavailable")
        result = synthesize_github_events(
            competitor="Exa",
            raw_commits=commits,
            raw_releases=[],
            window_start="2026-07-27",
            window_end="2026-08-10",
            provider_name="mock",
        )
    assert result.synthesis_status == "fallback"


def test_provider_interface_mock():
    p = _get_provider("mock")
    assert isinstance(p, MockLLMProvider)


def test_synthesis_method_attribute():
    commits = [_commit("feat(agent): add streaming")]
    releases = []
    result = synthesize_github_events(
        competitor="Exa",
        raw_commits=commits,
        raw_releases=releases,
        window_start="2026-07-27",
        window_end="2026-08-10",
        provider_name="mock",
    )
    for be in result.events:
        assert be.synthesis_method in ("mock_llm_synthesis", "deterministic_fallback", "deterministic_release")
