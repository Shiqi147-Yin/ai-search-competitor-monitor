"""test_topic_classification_exa.py
验证 Exa commit 的业务主题分类正确性。
"""
import pytest
from services.github_event_aggregator import _classify_topic


@pytest.mark.parametrize("title,expected_topic", [
    # sdk_release
    ("chore(master): release 2.17.0 (#242)", "sdk_release"),
    ("chore(master): release 2.16.2", "sdk_release"),
    ("Bump version to 3.4.0 across npm, plugin, and server manifests", "sdk_release"),
    # agent_runtime
    ("feat(agent): add max effort and budgets (#240)", "agent_runtime"),
    ("Make agent_run resumable with progress heartbeats", "agent_runtime"),
    ("Add Agent Plugins package metadata (#408)", "agent_runtime"),
    # maintenance
    ("fix: pin publish workflow to npm@11", "maintenance"),
    ("Pin Prettier 3.8.1, reformat TypeScript", "maintenance"),
    ("Add npm publish workflow (#404)", "maintenance"),
    ("Drop unused docs, Docker, and whoami. (#411)", "maintenance"),
    # developer_tooling
    ("Rewrite README for clearer install surfaces (#409)", "developer_tooling"),
    # sdk_api_change
    ("fix: update Category values and accept str at runtime (#237)", "sdk_api_change"),
    ("Update Category values and accept str at runtime", "sdk_api_change"),
])
def test_topic_classification(title, expected_topic):
    result = _classify_topic(title)
    assert result == expected_topic, f"title={title!r}: expected={expected_topic}, got={result}"
