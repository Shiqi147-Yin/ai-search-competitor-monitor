"""测试：GitHub 抓取结果字段映射"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from services.github_analyzer import (
    analyze_github_content,
    detect_github_event_type,
    extract_repo_name,
)


def test_repository_maps_correctly():
    url = "https://github.com/tavily-ai/tavily-python"
    assert detect_github_event_type(url) == "repository"
    assert extract_repo_name(url) == "tavily-ai/tavily-python"


def test_commit_maps_correctly():
    url = "https://github.com/exa-labs/exa-py/commit/abc123def"
    assert detect_github_event_type(url) == "commit"
    assert extract_repo_name(url) == "exa-labs/exa-py"


def test_release_maps_correctly():
    url = "https://github.com/tavily-ai/tavily-python/releases/tag/v2.0.0"
    assert detect_github_event_type(url) == "release"


def test_readme_docs_maps_to_docs():
    url = "https://github.com/exa-labs/exa-py/blob/main/README.md"
    assert detect_github_event_type(url) == "docs"


def test_docs_changed_does_not_trigger_capability_change():
    """docs_changed=True 不应自动使 capability_change=True。"""
    result = analyze_github_content(
        "https://github.com/org/repo/blob/main/README.md",
        title="Update README",
        content="readme quickstart installation",
    )
    assert result["docs_changed"] == 1
    assert result["capability_change"] == 0


def test_capability_change_does_not_trigger_integration_change():
    """capability_change=True 不应导致 integration_change=True（关键词不同）。"""
    result = analyze_github_content(
        "https://github.com/org/repo",
        title="Add streaming search mode and MCP support",
        content="new api streaming oauth performance",
    )
    assert result["capability_change"] == 1
    assert result["integration_change"] == 0


def test_integration_change_does_not_trigger_developer_experience_change():
    """integration_change=True 不因集成关键词触发 developer_experience_change。"""
    result = analyze_github_content(
        "https://github.com/org/repo",
        title="Add LangChain and CrewAI integration",
        content="new integration connector plugin langchain llamaindex",
    )
    assert result["integration_change"] == 1
    # dx 关键词没有出现
    assert result["developer_experience_change"] == 0


def test_all_four_flags_can_coexist():
    """四个标记可以同时为 True。"""
    result = analyze_github_content(
        "https://github.com/org/repo/blob/main/docs/quickstart.md",
        title="Add MCP SDK with LangChain integration quickstart guide",
        content="mcp oauth langchain quickstart example readme streaming integration",
    )
    assert result["docs_changed"] == 1
    assert result["capability_change"] == 1
    assert result["integration_change"] == 1
    assert result["developer_experience_change"] == 1


def test_change_summary_not_empty_for_all_types():
    """所有链接类型的 change_summary 均不为空字符串。"""
    test_cases = [
        "https://github.com/org/repo",
        "https://github.com/org/repo/commit/abc",
        "https://github.com/org/repo/releases/tag/v1.0",
        "https://github.com/org/repo/pull/42",
        "https://github.com/org/repo/blob/main/README.md",
    ]
    for url in test_cases:
        result = analyze_github_content(url, title="Test", content="test content")
        assert result["change_summary"], f"change_summary 为空，URL: {url}"


def test_skills_integrations_path_triggers_integration():
    """路径含 integrations 的 GitHub 链接，若内容含关键词能触发 integration_change。"""
    result = analyze_github_content(
        "https://github.com/org/repo/tree/main/integrations",
        title="Add new integrations for LangChain and Dify",
        content="integration plugin connector langchain dify",
    )
    assert result["integration_change"] == 1
