"""测试：页面类型识别"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from services.page_type_classifier import classify_page_type, is_entry_page, is_import_eligible


def test_homepage():
    assert classify_page_type("https://tavily.com") == "homepage"
    assert classify_page_type("https://www.tavily.com/") == "homepage"


def test_blog_index():
    assert classify_page_type("https://tavily.com/blog") == "blog_index"
    assert classify_page_type("https://www.tavily.com/blog") == "blog_index"


def test_detail_article():
    url = "https://www.tavily.com/blog/What-keyless-search-really-means-for-your-data"
    assert classify_page_type(url) == "detail_article"


def test_docs_index():
    assert classify_page_type("https://docs.tavily.com") == "docs_index"
    assert classify_page_type("https://docs.tavily.com/") == "docs_index"


def test_docs_detail():
    url = "https://docs.tavily.com/documentation/integrations/nemo-deepagents"
    assert classify_page_type(url) == "docs_detail"


def test_github_organization():
    assert classify_page_type("https://github.com/tavily-ai") == "github_organization"


def test_github_repository():
    assert classify_page_type("https://github.com/tavily-ai/tavily-mcp") == "github_repository"


def test_github_commit():
    url = "https://github.com/tavily-ai/tavily-mcp/commit/abc123"
    assert classify_page_type(url) == "github_commit"


def test_github_release():
    url = "https://github.com/tavily-ai/tavily-python/releases/tag/v2.0.0"
    assert classify_page_type(url) == "github_release"


def test_event_detail():
    assert classify_page_type("https://luma.com/tavily-h550") == "event_detail"


def test_aggregator():
    assert classify_page_type("https://advfn.com/news/tavily") == "aggregator"


def test_social_post():
    assert classify_page_type("https://x.com/TavilyHQ/status/123") == "social_post"


def test_entry_page_types():
    for url, expected_entry in [
        ("https://tavily.com", True),
        ("https://tavily.com/blog", True),
        ("https://docs.tavily.com", True),
        ("https://github.com/tavily-ai", True),
        ("https://github.com/tavily-ai/tavily-mcp", True),
        ("https://tavily.com/blog/keyless-search", False),
        ("https://github.com/tavily-ai/tavily-mcp/commit/abc", False),
    ]:
        pt = classify_page_type(url)
        assert is_entry_page(pt) == expected_entry, f"URL: {url}, pt: {pt}"


def test_import_eligible_types():
    for url, expected_eligible in [
        ("https://tavily.com/blog/keyless", True),
        ("https://docs.tavily.com/docs/integration", True),
        ("https://github.com/tavily-ai/tavily-mcp/commit/abc", True),
        ("https://luma.com/tavily-h550", True),
        ("https://tavily.com/blog", False),
        ("https://docs.tavily.com", False),
        ("https://github.com/tavily-ai", False),
    ]:
        pt = classify_page_type(url)
        assert is_import_eligible(pt) == expected_eligible, f"URL: {url}, pt: {pt}"
