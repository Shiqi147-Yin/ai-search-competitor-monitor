"""测试：GitHub 下钻"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import json
from unittest.mock import patch


_ATOM_COMMITS = """<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <title>Recent Commits to tavily-mcp:main</title>
  <entry>
    <title>feat: research streaming timeout handling</title>
    <author><name>alice</name></author>
    <updated>2026-07-10T08:00:00Z</updated>
    <link href="https://github.com/tavily-ai/tavily-mcp/commit/abc1234"/>
  </entry>
</feed>"""

_RELEASES_ATOM = """<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <entry>
    <title>v0.2.21</title>
    <updated>2026-07-10T08:00:00Z</updated>
    <link href="https://github.com/tavily-ai/tavily-mcp/releases/tag/v0.2.21"/>
  </entry>
</feed>"""


def _mock_github_get(url, accept="application/json"):
    if "atom" in url and "releases" in url:
        return (200, _RELEASES_ATOM)
    if "atom" in url:
        return (200, _ATOM_COMMITS)
    return (404, "")


def test_github_drilldown_repo_gets_commits():
    from services.source_drilldown import drilldown_github
    with patch("services.github_fetcher._get", side_effect=_mock_github_get):
        result = drilldown_github(
            "https://github.com/tavily-ai/tavily-mcp",
            "2026-07-08T00:00:00Z",
            "2026-07-21T00:00:00Z",
        )
    assert result.drilldown_status in ("success", "partial")
    commits = [it for it in result.discovered_items if it.page_type == "github_commit"]
    assert len(commits) >= 1


def test_github_repo_homepage_not_in_discovered():
    """仓库首页本身不作为子结果。"""
    from services.source_drilldown import drilldown_github
    with patch("services.github_fetcher._get", side_effect=_mock_github_get):
        result = drilldown_github(
            "https://github.com/tavily-ai/tavily-mcp",
            "2026-07-08T00:00:00Z",
            "2026-07-21T00:00:00Z",
        )
    urls = [it.source_url for it in result.discovered_items]
    assert "https://github.com/tavily-ai/tavily-mcp" not in urls


def test_commit_items_import_eligible():
    """Commit 子结果 import_eligible=True。"""
    from services.source_drilldown import drilldown_github
    with patch("services.github_fetcher._get", side_effect=_mock_github_get):
        result = drilldown_github(
            "https://github.com/tavily-ai/tavily-mcp",
            "2026-07-08T00:00:00Z",
            "2026-07-21T00:00:00Z",
        )
    commits = [it for it in result.discovered_items if it.page_type == "github_commit"]
    for c in commits:
        assert c.import_eligible


def test_single_failure_does_not_crash():
    """下钻失败不抛异常，返回 failed 状态。"""
    from services.source_drilldown import drilldown_github
    with patch("services.github_fetcher._get", side_effect=Exception("network error")):
        result = drilldown_github(
            "https://github.com/tavily-ai/tavily-mcp",
            "2026-07-08T00:00:00Z",
            "2026-07-21T00:00:00Z",
        )
    assert result.drilldown_status in ("partial", "failed")
