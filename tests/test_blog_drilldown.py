"""测试：Blog 下钻"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from unittest.mock import patch


_BLOG_HTML = """<html><body>
<article>
  <h2><a href="/blog/keyless-search-2026">What keyless search really means</a></h2>
  <time datetime="2026-07-14T10:00:00Z">July 14, 2026</time>
</article>
<article>
  <h2><a href="/blog/old-post">Old blog post</a></h2>
  <time datetime="2025-01-01T00:00:00Z">January 1, 2025</time>
</article>
</body></html>"""


def _mock_get(url, accept="text/html"):
    return (200, _BLOG_HTML)


def test_blog_drilldown_discovers_articles():
    from services.source_drilldown import drilldown_blog
    with patch("services.source_drilldown._get", side_effect=_mock_get):
        result = drilldown_blog(
            "https://www.tavily.com/blog",
            "2026-07-08T00:00:00Z",
            "2026-07-21T00:00:00Z",
        )
    assert result.drilldown_status in ("success", "partial")
    assert any("keyless" in (it.title or it.source_url).lower()
               for it in result.discovered_items)


def test_blog_index_itself_not_in_discovered():
    from services.source_drilldown import drilldown_blog
    with patch("services.source_drilldown._get", side_effect=_mock_get):
        result = drilldown_blog(
            "https://www.tavily.com/blog",
            "2026-07-08T00:00:00Z",
            "2026-07-21T00:00:00Z",
        )
    urls = [it.source_url for it in result.discovered_items]
    assert "https://www.tavily.com/blog" not in urls


def test_blog_only_window_items_marked():
    """有发布时间的文章：窗口内 = True；无发布时间的文章 within_window 可为 False。"""
    from services.source_drilldown import drilldown_blog
    with patch("services.source_drilldown._get", side_effect=_mock_get):
        result = drilldown_blog(
            "https://www.tavily.com/blog",
            "2026-07-08T00:00:00Z",
            "2026-07-21T00:00:00Z",
        )
    for item in result.discovered_items:
        if item.published_date and "2025" in item.published_date:
            assert not item.within_window
        if item.published_date and "2026-07-14" in item.published_date:
            assert item.within_window
        # 无发布时间的文章不强制断言 within_window


def test_blog_discovery_method():
    from services.source_drilldown import drilldown_blog
    with patch("services.source_drilldown._get", side_effect=_mock_get):
        result = drilldown_blog(
            "https://www.tavily.com/blog",
            "2026-07-08T00:00:00Z",
            "2026-07-21T00:00:00Z",
        )
    for item in result.discovered_items:
        assert item.discovery_method == "blog_index_drilldown"
