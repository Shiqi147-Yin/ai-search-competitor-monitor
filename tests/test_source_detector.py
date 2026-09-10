"""测试：来源平台和竞品识别（含修订规则）"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from services.source_detector import detect_competitor, detect_platform, detect_both


def test_tavily_competitor():
    assert detect_competitor("https://tavily.com/blog/post") == "Tavily"
    assert detect_competitor("https://docs.tavily.com/changelog") == "Tavily"
    assert detect_competitor("https://www.tavily.com/blog/keyless-search") == "Tavily"


def test_exa_competitor():
    assert detect_competitor("https://exa.ai/blog") == "Exa"
    assert detect_competitor("https://github.com/exa-labs/exa-py") == "Exa"


def test_brave_competitor():
    assert detect_competitor("https://brave.com/search-api") == "Brave"


def test_other_competitor():
    assert detect_competitor("https://openai.com/blog") == "Other"
    assert detect_competitor("https://github.com/langchain-ai/langchain") == "Other"


def test_github_platform():
    assert detect_platform("https://github.com/tavily-ai/tavily-python") == "GitHub"
    assert detect_platform("https://github.com/exa-labs/exa-py/releases") == "GitHub"


def test_x_platform():
    assert detect_platform("https://x.com/tavily_ai/status/123") == "X"
    assert detect_platform("https://twitter.com/ExaAILabs") == "X"


def test_linkedin_platform():
    assert detect_platform("https://linkedin.com/company/tavily") == "LinkedIn"


def test_discord_platform():
    assert detect_platform("https://discord.com/invite/abc") == "Discord"
    assert detect_platform("https://discord.gg/xyz") == "Discord"


def test_event_platform():
    assert detect_platform("https://lu.ma/event/xyz") == "Event"
    assert detect_platform("https://luma.com/tavily-h550") == "Event"


def test_tavily_blog_is_blog():
    """tavily.com/blog/* 应识别为 Blog，不是官网。"""
    assert detect_platform("https://www.tavily.com/blog/keyless-search") == "Blog"
    assert detect_platform("https://tavily.com/blog/post") == "Blog"


def test_docs_tavily_is_official():
    """docs.tavily.com/* 应识别为官网（技术文档），不是 Blog。"""
    assert detect_platform("https://docs.tavily.com/documentation/integrations/nemo") == "官网"
    assert detect_platform("https://docs.exa.ai/reference/getting-started") == "官网"


def test_luma_tavily_competitor():
    """luma.com URL 路径含 tavily → 竞品识别为 Tavily。"""
    assert detect_competitor("https://luma.com/tavily-h550") == "Tavily"
    assert detect_platform("https://luma.com/tavily-h550") == "Event"


def test_unknown_domain_returns_other():
    assert detect_platform("https://randomwebsite.io/page") == "Other"
    assert detect_competitor("https://randomwebsite.io") == "Other"

    # /blog/ on unknown domain → third-party blog
    assert detect_platform("https://randomwebsite.io/blog") == "第三方Blog"


def test_detect_both():
    result = detect_both("https://github.com/tavily-ai/tavily-python")
    assert result["competitor"] == "Tavily"
    assert result["source_platform"] == "GitHub"
