"""test_github_monitor.py
验证 GitHub 主动巡检逻辑（mock 网络请求）。
"""
import pytest
from unittest.mock import patch
from services.github_monitor import (
    monitor_repo_commits, monitor_repo_releases, run_github_monitor,
    GitHubCommitRecord, GitHubReleaseRecord,
)

_ATOM_COMMITS = """<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <entry>
    <title>Add streaming support for Research tool</title>
    <author><name>alice</name></author>
    <updated>2026-07-10T12:00:00Z</updated>
    <link href="https://github.com/tavily-ai/tavily-mcp/commit/abc1234"/>
  </entry>
  <entry>
    <title>Fix timeout handling in Research</title>
    <author><name>bob</name></author>
    <updated>2026-07-10T14:00:00Z</updated>
    <link href="https://github.com/tavily-ai/tavily-mcp/commit/def5678"/>
  </entry>
  <entry>
    <title>Old commit outside window</title>
    <author><name>carol</name></author>
    <updated>2026-07-01T10:00:00Z</updated>
    <link href="https://github.com/tavily-ai/tavily-mcp/commit/old0001"/>
  </entry>
</feed>"""

_ATOM_RELEASES = """<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <entry>
    <title>v0.5.0</title>
    <updated>2026-07-12T08:00:00Z</updated>
    <link href="https://github.com/tavily-ai/tavily-mcp/releases/tag/v0.5.0"/>
  </entry>
</feed>"""


def test_monitor_commits_within_window():
    with patch("services.github_monitor._get") as mock_get:
        def side_effect(url, accept="application/json"):
            if "atom" in url:
                return 200, _ATOM_COMMITS
            return 404, ""
        mock_get.side_effect = side_effect

        commits = monitor_repo_commits("tavily-ai", "tavily-mcp", "2026-07-08", "2026-07-17")

    assert len(commits) == 2
    assert all(c.commit_date >= "2026-07-08" for c in commits)
    assert all(c.repository == "tavily-ai/tavily-mcp" for c in commits)


def test_monitor_commits_excludes_outside_window():
    with patch("services.github_monitor._get") as mock_get:
        def side_effect(url, accept="application/json"):
            if "atom" in url:
                return 200, _ATOM_COMMITS
            return 404, ""
        mock_get.side_effect = side_effect

        commits = monitor_repo_commits("tavily-ai", "tavily-mcp", "2026-07-08", "2026-07-17")

    urls = [c.commit_url for c in commits]
    assert not any("old0001" in u for u in urls), "窗口外 commit 不应被返回"


def test_monitor_releases_within_window():
    with patch("services.github_monitor._get") as mock_get:
        def side_effect(url, accept="application/json"):
            if "releases.atom" in url:
                return 200, _ATOM_RELEASES
            return 404, ""
        mock_get.side_effect = side_effect

        releases = monitor_repo_releases("tavily-ai", "tavily-mcp", "2026-07-08", "2026-07-17")

    assert len(releases) == 1
    assert releases[0].version == "v0.5.0"


def test_repo_homepage_not_returned_as_commit():
    """仓库首页 URL 不得被作为 commit 返回。"""
    with patch("services.github_monitor._get") as mock_get:
        mock_get.return_value = 200, _ATOM_COMMITS

        commits = monitor_repo_commits("tavily-ai", "tavily-mcp", "2026-07-08", "2026-07-17")

    homepage = "https://github.com/tavily-ai/tavily-mcp"
    assert not any(c.commit_url == homepage for c in commits)


def test_single_repo_failure_does_not_abort_others():
    """一个仓库失败不影响其他仓库。"""
    call_count = {"n": 0}

    def side_effect(url, accept="application/json"):
        call_count["n"] += 1
        if "tavily-mcp" in url:
            raise ConnectionError("模拟网络错误")
        if "atom" in url:
            return 200, _ATOM_COMMITS
        return 404, ""

    github_config = {
        "owner": "tavily-ai",
        "repositories": [
            {"name": "tavily-mcp", "monitor": ["commits", "releases"]},
            {"name": "tavily-python", "monitor": ["commits"]},
        ],
    }
    with patch("services.github_monitor._get", side_effect=side_effect):
        result = run_github_monitor("Tavily", github_config, "2026-07-08", "2026-07-17")

    assert len(result["errors"]) >= 1
    errors_repos = [e["repository"] for e in result["errors"]]
    assert any("tavily-mcp" in r for r in errors_repos)
    # 程序不应崩溃，errors 结构完整
    assert "commits" in result
    assert "releases" in result


def test_run_github_monitor_returns_expected_structure():
    github_config = {
        "owner": "tavily-ai",
        "repositories": [{"name": "tavily-mcp", "monitor": ["commits", "releases"]}],
    }
    with patch("services.github_monitor._get") as mock_get:
        def side_effect(url, accept="application/json"):
            if "releases.atom" in url:
                return 200, _ATOM_RELEASES
            if "atom" in url:
                return 200, _ATOM_COMMITS
            return 404, ""
        mock_get.side_effect = side_effect

        result = run_github_monitor("Tavily", github_config, "2026-07-08", "2026-07-17")

    assert "commits" in result
    assert "releases" in result
    assert "errors" in result
    assert len(result["commits"]) == 2
    assert len(result["releases"]) == 1
