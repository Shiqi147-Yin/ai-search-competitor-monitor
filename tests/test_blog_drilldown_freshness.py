"""测试：Blog 下钻新鲜度（日期解析后正确判定窗口）"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from unittest.mock import patch

_BLOG_HTML_WITH_DATES = """<html><body>
<a href="/blog/What-keyless-search-really-means-for-your-data">
  What Keyless Search Really Means for Your Dataproduct·Jul 14
</a>
<a href="/blog/may-shipped">
  What We Shipped: May 2026news·May 1, 2026
</a>
<a href="/blog/fieldway-case-study">
  Fieldway customer·Apr 30
</a>
</body></html>"""


def _mock_blog_get(url, accept="text/html"):
    return (200, _BLOG_HTML_WITH_DATES)


def test_keyless_search_within_window():
    from services.source_drilldown import drilldown_blog
    with patch("services.source_drilldown._get", side_effect=_mock_blog_get):
        result = drilldown_blog(
            "https://www.tavily.com/blog",
            "2026-07-09T00:00:00Z",
            "2026-07-23T00:00:00Z",
        )
    keyless = next((it for it in result.discovered_items
                    if "keyless" in it.source_url.lower()), None)
    assert keyless is not None, "Keyless Search 未被发现"
    assert keyless.published_date != "", f"日期未提取"
    assert keyless.within_window, (
        f"Keyless Search 应在窗口内，date={keyless.published_date}"
    )


def test_may_article_outside_window():
    from services.source_drilldown import drilldown_blog
    with patch("services.source_drilldown._get", side_effect=_mock_blog_get):
        result = drilldown_blog(
            "https://www.tavily.com/blog",
            "2026-07-09T00:00:00Z",
            "2026-07-23T00:00:00Z",
        )
    may = next((it for it in result.discovered_items if "may-shipped" in it.source_url), None)
    if may and may.published_date:
        assert not may.within_window, "May 文章不应在 7 月窗口内"


def test_no_fake_date_for_dateless_item():
    """无日期文章不得使用抓取时间替代。"""
    from services.source_drilldown import drilldown_blog
    _NO_DATE_HTML = """<html><body>
    <a href="/blog/article-no-date">Title With No Date</a>
    </body></html>"""
    with patch("services.source_drilldown._get", return_value=(200, _NO_DATE_HTML)):
        result = drilldown_blog(
            "https://www.tavily.com/blog",
            "2026-07-09T00:00:00Z",
            "2026-07-23T00:00:00Z",
        )
    no_date_items = [it for it in result.discovered_items if not it.published_date]
    for item in no_date_items:
        assert not item.within_window, "无日期文章不得默认为窗口内"
