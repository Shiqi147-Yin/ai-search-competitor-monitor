"""测试：GitHub URL 解析器"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from services.github_url_parser import parse_github_url


def test_parse_repository():
    info = parse_github_url("https://github.com/tavily-ai/tavily-python")
    assert info.url_type == "repository"
    assert info.owner == "tavily-ai"
    assert info.repo == "tavily-python"


def test_parse_commits_with_branch():
    url = "https://github.com/tavily-ai/tavily-mcp/commits/main"
    info = parse_github_url(url)
    assert info.url_type == "commits"
    assert info.owner == "tavily-ai"
    assert info.repo == "tavily-mcp"
    assert info.branch == "main"


def test_parse_commits_since_until():
    url = "https://github.com/tavily-ai/tavily-mcp/commits/main/?since=2026-07-08&until=2026-07-16"
    info = parse_github_url(url)
    assert info.url_type == "commits"
    assert info.since == "2026-07-08"
    assert info.until == "2026-07-16"
    assert "since=2026-07-08" in (info.api_url or "")


def test_parse_single_commit():
    url = "https://github.com/exa-labs/exa-py/commit/abc123def456"
    info = parse_github_url(url)
    assert info.url_type == "commit"
    assert info.sha == "abc123def456"


def test_parse_release():
    url = "https://github.com/tavily-ai/tavily-python/releases/tag/v2.0.0"
    info = parse_github_url(url)
    assert info.url_type == "release"
    assert info.tag == "v2.0.0"
    assert info.atom_feed_url != ""


def test_parse_pr():
    url = "https://github.com/org/repo/pull/42"
    info = parse_github_url(url)
    assert info.url_type == "pr"
    assert info.pr_number == "42"


def test_parse_issue():
    url = "https://github.com/org/repo/issues/10"
    info = parse_github_url(url)
    assert info.url_type == "issue"
    assert info.issue_number == "10"


def test_parse_readme_docs():
    url = "https://github.com/org/repo/blob/main/README.md"
    info = parse_github_url(url)
    assert info.url_type == "docs"
    assert info.file_path == "README.md"
    assert "raw.githubusercontent.com" in info.raw_url


def test_parse_docs_directory():
    url = "https://github.com/org/repo/tree/main/docs/quickstart"
    info = parse_github_url(url)
    assert info.url_type in ("docs", "tree")


def test_parse_non_github_url():
    info = parse_github_url("https://exa.ai/blog/post")
    assert info.owner == ""
    assert info.repo == ""
    assert info.url_type == "unknown"


def test_atom_feed_url_generated_for_commits():
    url = "https://github.com/tavily-ai/tavily-mcp/commits/main"
    info = parse_github_url(url)
    assert info.atom_feed_url != ""
    assert "atom" in info.atom_feed_url
