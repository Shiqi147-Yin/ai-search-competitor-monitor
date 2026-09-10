"""测试：入口页默认不选，具体内容页可选"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from services.page_type_classifier import (
    classify_page_type, is_entry_page, is_import_eligible, ENTRY_PAGE_TYPES
)


def test_blog_index_not_default_selected():
    pt = classify_page_type("https://tavily.com/blog")
    assert is_entry_page(pt)
    assert not is_import_eligible(pt)


def test_github_repo_not_default_selected():
    pt = classify_page_type("https://github.com/tavily-ai/tavily-mcp")
    assert is_entry_page(pt)
    assert not is_import_eligible(pt)


def test_blog_article_eligible():
    pt = classify_page_type("https://tavily.com/blog/keyless-search")
    assert not is_entry_page(pt)
    assert is_import_eligible(pt)


def test_github_commit_eligible():
    pt = classify_page_type("https://github.com/tavily-ai/tavily-mcp/commit/abc")
    assert not is_entry_page(pt)
    assert is_import_eligible(pt)


def test_event_detail_eligible():
    pt = classify_page_type("https://luma.com/tavily-h550")
    assert not is_entry_page(pt)
    assert is_import_eligible(pt)


def test_docs_detail_eligible():
    pt = classify_page_type("https://docs.tavily.com/documentation/integrations/nemo")
    assert not is_entry_page(pt)
    assert is_import_eligible(pt)


def test_all_entry_types_not_eligible():
    # 每种入口类型都不可直接导入
    for pt in ENTRY_PAGE_TYPES:
        assert not is_import_eligible(pt), f"Entry page type {pt} should not be import_eligible"
