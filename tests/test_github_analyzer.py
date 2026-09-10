"""测试：GitHub 专项分析"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from services.github_analyzer import (
    detect_github_event_type,
    extract_repo_name,
    analyze_github_content,
    build_change_summary,
)


def test_repo_url_type():
    assert detect_github_event_type("https://github.com/tavily-ai/tavily-python") == "repository"


def test_commit_url_type():
    assert detect_github_event_type("https://github.com/exa-labs/exa-py/commit/abc123") == "commit"


def test_release_url_type():
    assert detect_github_event_type("https://github.com/tavily-ai/tavily-python/releases/tag/v1.0") == "release"


def test_pr_url_type():
    assert detect_github_event_type("https://github.com/org/repo/pull/42") == "pr"


def test_issue_url_type():
    assert detect_github_event_type("https://github.com/org/repo/issues/10") == "issue"


def test_docs_url_type():
    assert detect_github_event_type("https://github.com/org/repo/blob/main/docs/quickstart.md") == "docs"
    assert detect_github_event_type("https://github.com/org/repo/blob/main/README.md") == "docs"


def test_readme_update_marks_docs_changed():
    result = analyze_github_content(
        "https://github.com/org/repo/blob/main/README.md",
        title="Update README with installation guide",
    )
    assert result["docs_changed"] == 1


def test_streaming_mcp_marks_capability():
    result = analyze_github_content(
        "https://github.com/tavily-ai/tavily-python",
        title="Add MCP support and streaming search mode",
        content="New streaming endpoint with oauth authentication",
    )
    assert result["capability_change"] == 1


def test_langchain_kiro_marks_integration():
    result = analyze_github_content(
        "https://github.com/exa-labs/exa-py",
        title="Add LangChain integration and Kiro skill",
        content="New connector for CrewAI and Dify",
    )
    assert result["integration_change"] == 1


def test_quickstart_example_marks_dx():
    result = analyze_github_content(
        "https://github.com/org/repo/blob/main/docs/quickstart.md",
        title="Add quickstart guide and installation tutorial",
    )
    assert result["developer_experience_change"] == 1


def test_pure_doc_change_does_not_force_capability():
    """纯文档修改不应强制标记为产品能力升级。"""
    result = analyze_github_content(
        "https://github.com/org/repo/blob/main/README.md",
        title="Fix typo in README",
        content="corrected spelling in the readme file",
    )
    assert result["capability_change"] == 0


def test_change_summary_not_empty():
    result = analyze_github_content(
        "https://github.com/tavily-ai/tavily-python/releases/tag/v2.0",
        title="v2.0 Release: New SDK with streaming support",
    )
    assert result["change_summary"]
    assert len(result["change_summary"]) > 0


def test_extract_repo_name():
    assert extract_repo_name("https://github.com/tavily-ai/tavily-python") == "tavily-ai/tavily-python"
    assert extract_repo_name("https://github.com/exa-labs/exa-py/commit/abc") == "exa-labs/exa-py"
