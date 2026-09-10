"""测试：GitHub 专项抓取（使用 mock，不依赖真实网络）"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import json
from unittest.mock import patch, MagicMock

from services.github_fetcher import fetch_github, _parse_commits_atom


_ATOM_COMMITS = """<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <title>Recent Commits to tavily-mcp:main</title>
  <entry>
    <title>Add streaming support for search results</title>
    <author><name>alice</name></author>
    <updated>2026-07-15T10:00:00Z</updated>
    <link href="https://github.com/tavily-ai/tavily-mcp/commit/abc1234"/>
  </entry>
  <entry>
    <title>Fix README typo</title>
    <author><name>bob</name></author>
    <updated>2026-07-14T08:00:00Z</updated>
    <link href="https://github.com/tavily-ai/tavily-mcp/commit/def5678"/>
  </entry>
</feed>"""

_API_COMMITS = [
    {
        "sha": "abc1234567890",
        "commit": {
            "message": "Add streaming support",
            "author": {"name": "alice", "date": "2026-07-15T10:00:00Z"},
        },
    },
    {
        "sha": "def5678901234",
        "commit": {
            "message": "Fix typo in README",
            "author": {"name": "bob", "date": "2026-07-14T08:00:00Z"},
        },
    },
]


def _make_resp(status, text, url="https://github.com/x"):
    r = MagicMock()
    r.status_code = status
    r.text = text
    r.url = url
    r.headers = {}
    return r


def test_atom_feed_parsed_successfully():
    """Atom feed 正常返回时能提取提交列表。"""
    commits = _parse_commits_atom(_ATOM_COMMITS)
    assert len(commits) == 2
    assert commits[0].title == "Add streaming support for search results"
    assert commits[0].sha != ""
    assert commits[0].date == "2026-07-15"


def test_commits_via_atom_feed():
    """通过 Atom feed 获取提交列表，status=success。"""
    with patch("services.github_fetcher._get") as mock_get:
        mock_get.return_value = (200, _ATOM_COMMITS)
        result = fetch_github("https://github.com/tavily-ai/tavily-mcp/commits/main")

    assert result.status == "success"
    assert len(result.commits) >= 1
    assert result.commits[0].title != ""


def test_api_fallback_when_atom_fails():
    """Atom feed 失败时降级到 API。"""
    call_count = {"n": 0}

    def _side_effect(url, accept="application/json"):
        call_count["n"] += 1
        if "atom" in url:
            return (404, "not found")
        return (200, json.dumps(_API_COMMITS))

    with patch("services.github_fetcher._get", side_effect=_side_effect):
        result = fetch_github("https://github.com/tavily-ai/tavily-mcp/commits/main")

    assert result.status == "success"
    assert call_count["n"] >= 2


def test_api_403_preserves_error_not_404():
    """API 返回 403（rate limit）时记录具体错误，不误判为仓库不存在。"""
    with patch("services.github_fetcher._get") as mock_get:
        mock_get.return_value = (403, "rate limit exceeded")
        result = fetch_github("https://github.com/tavily-ai/tavily-mcp/commits/main")

    assert "403" in result.error or "rate" in result.error.lower()
    # 关键：不应只显示"不存在"（即错误信息里能区分 rate limit 和仓库不存在）
    assert "rate" in result.error.lower() or "403" in result.error


def test_raw_readme_fetchable():
    """raw README 能被获取并保存到 readme_content 或 content_snippet。"""
    readme_content = "# Tavily MCP\nThis is the README content."

    def _side_effect(url, accept="application/json"):
        if "raw.githubusercontent.com" in url:
            return (200, readme_content)
        return (404, "not found")

    with patch("services.github_fetcher._get", side_effect=_side_effect):
        result = fetch_github("https://github.com/tavily-ai/tavily-mcp/blob/main/README.md")

    assert result.status == "success"
    assert "README" in (result.readme_content or result.content_snippet or result.title or "")


def test_single_failure_does_not_crash():
    """单条抓取失败不抛未捕获异常，返回 failed 状态。"""
    with patch("services.github_fetcher._get", side_effect=Exception("network error")):
        result = fetch_github("https://github.com/org/repo/commits/main")

    assert result.status == "failed"
    assert result.url == "https://github.com/org/repo/commits/main"


def test_no_token_required():
    """不依赖 Token 也能运行（匿名请求，成功或受限均可接受）。"""
    with patch("services.github_fetcher._get") as mock_get:
        mock_get.return_value = (200, json.dumps(_API_COMMITS))
        result = fetch_github("https://github.com/tavily-ai/tavily-mcp/commits/main")

    # 只要不崩溃且有结果即可
    assert result.status in ("success", "partial", "failed", "restricted")
