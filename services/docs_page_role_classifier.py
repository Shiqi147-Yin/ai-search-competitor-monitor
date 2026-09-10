"""Docs 页面价值分类器
根据 URL 路径和页面标题判断 Docs 页面的功能角色（page_role）。
决定该页面是否为高价值内容页（integration/changelog/sdk/mcp/api）
还是通用低价值页面（faq/welcome/navigation）。
"""
import re
from urllib.parse import urlparse


# ── 角色匹配规则（优先级从高到低）────────────────────────────────
ROLE_PATTERNS: dict[str, list[str]] = {
    "integration": [
        "integration", "integrations", "nemo", "nvidia", "langchain",
        "composio", "agno", "llamaindex", "llama-index", "autogen",
        "camelai", "crewai", "dify", "flowise", "haystack", "openai",
        "anthropic", "mistral", "gemini", "vertexai", "huggingface",
    ],
    "changelog": [
        "changelog", "release-notes", "release_notes", "what-is-new",
        "whatsnew", "whats-new", "releases",
    ],
    "api_reference": [
        "api-reference", "api_reference", "/api/", "openapi",
        "rest-api", "rest_api", "endpoints", "reference",
    ],
    "sdk": [
        "sdk", "python-sdk", "js-sdk", "typescript-sdk", "node-sdk",
        "go-sdk", "rust-sdk", "java-sdk",
    ],
    "mcp": [
        "mcp", "model-context-protocol", "tavily-mcp",
    ],
    "guide": [
        "guide", "guides", "tutorial", "tutorials", "quickstart",
        "quick-start", "getting-started", "getting_started", "how-to",
        "howto",
    ],
    "faq": [
        "faq", "faqs", "frequently-asked", "frequently_asked",
        "troubleshoot", "troubleshooting",
    ],
    "welcome": [
        "welcome", "introduction", "intro", "overview",
    ],
    "navigation": [
        "sitemap", "/index",
    ],
}

# 通用低价值页面（默认不生成竞品动态）
GENERIC_PAGE_ROLES: frozenset[str] = frozenset({
    "faq", "welcome", "navigation", "generic",
})

# 高价值页面（首次发现也进入待确认）
HIGH_VALUE_ROLES: frozenset[str] = frozenset({
    "integration", "changelog", "api_reference", "sdk", "mcp",
})

# 角色优先级顺序（越靠前优先级越高）
_ROLE_PRIORITY: list[str] = [
    "integration", "changelog", "mcp", "sdk", "api_reference",
    "guide", "faq", "welcome", "navigation", "generic",
]


def classify_docs_page_role(url: str, title: str = "") -> tuple[str, bool]:
    """判断 Docs 页面的角色和是否为通用低价值页面。

    Args:
        url:   页面 URL
        title: 页面标题（可选，用于辅助判断）

    Returns:
        (role, is_generic_page)
        role: 'integration' | 'changelog' | 'api_reference' | 'sdk' | 'mcp' |
              'guide' | 'faq' | 'welcome' | 'navigation' | 'generic'
        is_generic_page: True 表示默认不生成竞品动态
    """
    path = urlparse(url).path.lower().rstrip("/")
    combined = f"{path} {title.lower()}"

    matched_roles: list[str] = []
    for role, keywords in ROLE_PATTERNS.items():
        for kw in keywords:
            if kw in combined:
                matched_roles.append(role)
                break

    if not matched_roles:
        return "generic", True

    # 按优先级选最高优先级角色
    for role in _ROLE_PRIORITY:
        if role in matched_roles:
            is_generic = role in GENERIC_PAGE_ROLES
            return role, is_generic

    return "generic", True


def is_high_value(role: str) -> bool:
    """判断 Docs 页面角色是否属于高价值类型。"""
    return role in HIGH_VALUE_ROLES


def is_generic(role: str) -> bool:
    """判断 Docs 页面角色是否为通用低价值类型。"""
    return role in GENERIC_PAGE_ROLES
