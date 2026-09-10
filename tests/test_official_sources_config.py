"""test_official_sources_config.py
验证 official_monitoring_sources.yaml 配置正确，且页面代码中无硬编码入口 URL。
"""
import os
import re
import pytest
import yaml


_CONFIG_PATH = os.path.join(
    os.path.dirname(__file__), "..", "config", "official_monitoring_sources.yaml"
)
_PAGES_DIR = os.path.join(os.path.dirname(__file__), "..", "pages")


@pytest.fixture(scope="module")
def config():
    with open(_CONFIG_PATH, encoding="utf-8") as f:
        return yaml.safe_load(f)


def test_tavily_section_exists(config):
    assert "Tavily" in config, "Tavily 配置段缺失"


def test_tavily_blog_entry(config):
    blog = config["Tavily"]["website"].get("blog", [])
    assert len(blog) >= 1, "Tavily blog 入口不能为空"
    assert any("tavily.com/blog" in u for u in blog), "Tavily blog 入口不正确"


def test_tavily_docs_entry(config):
    docs = config["Tavily"]["website"].get("docs", [])
    assert len(docs) >= 1
    assert any("docs.tavily.com" in u for u in docs)


def test_tavily_integrations_entry(config):
    integrations = config["Tavily"]["website"].get("integrations", [])
    assert len(integrations) >= 1
    assert any("integrations" in u for u in integrations)


def test_tavily_sitemap_entry(config):
    sitemaps = config["Tavily"]["website"].get("sitemap", [])
    assert len(sitemaps) >= 2
    assert any("sitemap.xml" in u for u in sitemaps)


def test_tavily_github_owner(config):
    owner = config["Tavily"]["github"].get("owner", "")
    assert owner == "tavily-ai", f"GitHub owner 应为 tavily-ai，实际为 {owner}"


def test_tavily_github_repositories(config):
    repos = config["Tavily"]["github"].get("repositories", [])
    names = [r["name"] for r in repos]
    assert "tavily-mcp" in names, "tavily-mcp 仓库缺失"
    assert "tavily-python" in names, "tavily-python 仓库缺失"


def test_tavily_mcp_priority(config):
    repos = config["Tavily"]["github"]["repositories"]
    mcp = next((r for r in repos if r["name"] == "tavily-mcp"), None)
    assert mcp is not None
    assert mcp.get("priority") == "high"


def test_tavily_mcp_monitor_includes_commits_and_releases(config):
    repos = config["Tavily"]["github"]["repositories"]
    mcp = next((r for r in repos if r["name"] == "tavily-mcp"), None)
    monitor = mcp.get("monitor", [])
    assert "commits" in monitor
    assert "releases" in monitor


def test_config_supports_exa_extension():
    """配置格式与 Tavily 同层级，可以直接扩展 Exa/Brave。"""
    with open(_CONFIG_PATH, encoding="utf-8") as f:
        raw = f.read()
    # 注释中应包含 Exa/Brave 的占位符说明
    assert "Exa" in raw or "exa" in raw.lower(), "配置文件应包含 Exa 扩展说明"


def test_pages_no_hardcoded_tavily_blog_url():
    """pages/ 目录下的代码不得硬编码官方入口 URL。"""
    hardcoded_patterns = [
        r'["\']https://www\.tavily\.com/blog["\']',
        r'["\']https://docs\.tavily\.com/["\']',
    ]
    offending = []
    for fname in os.listdir(_PAGES_DIR):
        if not fname.endswith(".py"):
            continue
        fpath = os.path.join(_PAGES_DIR, fname)
        with open(fpath, encoding="utf-8") as f:
            content = f.read()
        for pat in hardcoded_patterns:
            if re.search(pat, content):
                offending.append(f"{fname}: {pat}")

    assert not offending, (
        "以下页面文件硬编码了官方入口 URL（应从配置读取）:\n"
        + "\n".join(offending)
    )
