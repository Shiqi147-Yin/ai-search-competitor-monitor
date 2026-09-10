"""test_docs_page_role.py
验证 docs_page_role_classifier 能正确识别各类 Docs 页面角色。
"""
import pytest
from services.docs_page_role_classifier import classify_docs_page_role, is_high_value, is_generic


@pytest.mark.parametrize("url,title,expected_role,expected_generic", [
    # integration 类：高价值
    ("https://docs.tavily.com/documentation/integrations/nemo", "NVIDIA NeMo Deep Agents", "integration", False),
    ("https://docs.tavily.com/documentation/integrations/langchain", "LangChain Integration", "integration", False),
    ("https://docs.tavily.com/documentation/integrations", "Integrations", "integration", False),
    # changelog 类：高价值
    ("https://docs.tavily.com/changelog", "Changelog", "changelog", False),
    ("https://docs.tavily.com/release-notes", "Release Notes", "changelog", False),
    # api_reference 类：高价值
    ("https://docs.tavily.com/api-reference/endpoint", "API Reference", "api_reference", False),
    # sdk 类：高价值
    ("https://docs.tavily.com/sdk/python-sdk", "Python SDK", "sdk", False),
    # mcp 类：高价值
    ("https://docs.tavily.com/mcp", "Tavily MCP", "mcp", False),
    # guide 类：中价值
    ("https://docs.tavily.com/quickstart", "Quickstart Guide", "guide", False),
    ("https://docs.tavily.com/getting-started", "Getting Started", "guide", False),
    # faq 类：通用低价值
    ("https://docs.tavily.com/faq", "FAQ", "faq", True),
    ("https://docs.tavily.com/troubleshooting", "Troubleshooting", "faq", True),
    # welcome 类：通用低价值
    ("https://docs.tavily.com/welcome", "Welcome to Tavily", "welcome", True),
    ("https://docs.tavily.com/introduction", "Introduction", "welcome", True),
    ("https://docs.tavily.com/overview", "Overview", "welcome", True),
    # 未知 → generic
    ("https://docs.tavily.com/some-random-page", "Some Page", "generic", True),
])
def test_classify_docs_page_role(url, title, expected_role, expected_generic):
    role, is_gen = classify_docs_page_role(url, title)
    assert role == expected_role, f"URL={url}: 期望 {expected_role}，实际 {role}"
    assert is_gen == expected_generic, f"URL={url}: 期望 is_generic={expected_generic}，实际 {is_gen}"


def test_nemo_is_integration():
    role, is_gen = classify_docs_page_role(
        "https://docs.tavily.com/documentation/integrations/nemo",
        "NVIDIA NeMo Deep Agents"
    )
    assert role == "integration"
    assert not is_gen
    assert is_high_value(role)


def test_faq_is_generic():
    role, is_gen = classify_docs_page_role(
        "https://docs.tavily.com/faq",
        "Frequently Asked Questions"
    )
    assert role == "faq"
    assert is_gen
    assert is_generic(role)


def test_welcome_is_generic():
    role, is_gen = classify_docs_page_role(
        "https://docs.tavily.com/welcome",
        "Welcome"
    )
    assert is_gen
    assert is_generic(role)


def test_changelog_is_high_value():
    role, _ = classify_docs_page_role(
        "https://docs.tavily.com/changelog",
        "Changelog"
    )
    assert is_high_value(role)


def test_empty_url_returns_generic():
    role, is_gen = classify_docs_page_role("", "")
    assert role == "generic"
    assert is_gen
