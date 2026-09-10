"""测试：下钻流水线（单条失败不影响批次，不递归，无重复）"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
from unittest.mock import patch
from services.source_drilldown import drilldown_result, DiscoveredItem


def _blog_result(url, title="Blog Index"):
    return {"source_url": url, "title": title, "page_type": "blog_index"}


def _article_result(url, title="Article"):
    return {"source_url": url, "title": title, "page_type": "detail_article"}


def _mock_blog_items(n=3):
    """返回 n 条具体文章的下钻结果。"""
    from services.source_drilldown import DrilldownResult
    items = [
        DiscoveredItem(
            source_url=f"https://tavily.com/blog/article-{i}",
            title=f"Article {i}",
            page_type="detail_article",
            discovery_method="blog_index_drilldown",
            import_eligible=True,
            within_window=True,
        )
        for i in range(n)
    ]
    return DrilldownResult(source_url="https://tavily.com/blog",
                            page_type="blog_index",
                            drilldown_status="success",
                            discovered_items=items)


def test_entry_page_triggers_drilldown():
    """入口页触发下钻，not_needed 不触发。"""
    with patch("services.source_drilldown.drilldown_blog", return_value=_mock_blog_items(2)):
        result = drilldown_result(
            _blog_result("https://tavily.com/blog"),
            "2026-07-08T00:00:00Z",
            "2026-07-21T00:00:00Z",
        )
    assert result.drilldown_status == "success"
    assert len(result.discovered_items) == 2


def test_detail_page_returns_not_needed():
    """具体内容页不触发下钻。"""
    result = drilldown_result(
        _article_result("https://tavily.com/blog/keyless"),
        "2026-07-08T00:00:00Z",
        "2026-07-21T00:00:00Z",
    )
    assert result.drilldown_status == "not_needed"
    assert len(result.discovered_items) == 0


def test_single_drilldown_failure_does_not_crash():
    """单个下钻失败不抛异常。"""
    with patch("services.source_drilldown.drilldown_blog", side_effect=Exception("Network error")):
        try:
            drilldown_result(
                _blog_result("https://tavily.com/blog"),
                "2026-07-08T00:00:00Z",
                "2026-07-21T00:00:00Z",
            )
        except Exception as e:
            pytest.fail(f"drilldown_result 抛出了异常: {e}")


def test_no_recursive_drilldown():
    """下钻结果的子项不再触发二次下钻（depth=1 限制）。"""
    with patch("services.source_drilldown.drilldown_blog", return_value=_mock_blog_items(2)):
        result = drilldown_result(
            _blog_result("https://tavily.com/blog"),
            "2026-07-08T00:00:00Z",
            "2026-07-21T00:00:00Z",
        )
    for item in result.discovered_items:
        assert item.page_type != "blog_index", "下钻结果不应再是入口页"
