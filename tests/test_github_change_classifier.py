"""测试：GitHub 变更分类器（区分文档/能力/集成/开发者体验）"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from services.github_analyzer import analyze_github_content


def test_readme_typo_fix_not_capability():
    """README 修复错别字，不标记为产品能力升级。"""
    result = analyze_github_content(
        "https://github.com/org/repo/blob/main/README.md",
        title="Fix typo in README",
        content="corrected spelling mistakes in the readme file",
    )
    assert result["capability_change"] == 0
    assert result["docs_changed"] == 1


def test_streaming_doc_marks_capability():
    """Streaming 文档更新标记 capability_change。"""
    result = analyze_github_content(
        "https://github.com/org/repo",
        title="Add streaming search mode documentation",
        content="new streaming api mode with real-time results and mcp support",
    )
    assert result["capability_change"] == 1


def test_kiro_integration_marks_integration():
    """Kiro 集成标记 integration_change。"""
    result = analyze_github_content(
        "https://github.com/org/repo",
        title="Add Kiro and NVIDIA integration support",
        content="new integration for kiro coding agent and nvidia cerebras",
    )
    assert result["integration_change"] == 1


def test_quickstart_marks_developer_experience():
    """Quickstart 更新标记 developer_experience_change。"""
    result = analyze_github_content(
        "https://github.com/org/repo/blob/main/docs/quickstart.md",
        title="Add installation guide and quickstart tutorial",
        content="quickstart example installation guide for new users",
    )
    assert result["developer_experience_change"] == 1


def test_multiple_changes_can_coexist():
    """多个变化可同时标记为 True。"""
    result = analyze_github_content(
        "https://github.com/org/repo",
        title="Add MCP + LangChain integration with quickstart guide",
        content="mcp streaming langchain integration quickstart example readme",
    )
    assert result["capability_change"] == 1
    assert result["integration_change"] == 1
    assert result["developer_experience_change"] == 1


def test_docs_changed_independent_of_capability():
    """docs_changed 和 capability_change 相互独立，不互相触发。"""
    # 纯 README 更新，无能力关键词
    r1 = analyze_github_content(
        "https://github.com/org/repo/blob/main/README.md",
        title="Update README formatting",
        content="fixed indentation and added badges to readme",
    )
    assert r1["docs_changed"] == 1
    assert r1["capability_change"] == 0

    # 纯能力更新，无文档路径
    r2 = analyze_github_content(
        "https://github.com/org/repo",
        title="New streaming API endpoint",
        content="added streaming search mode with new api",
    )
    assert r2["capability_change"] == 1
