"""测试：Docs 下钻"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from unittest.mock import patch


_SITEMAP_XML = """<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <url>
    <loc>https://docs.tavily.com/</loc>
    <lastmod>2026-07-21</lastmod>
  </url>
  <url>
    <loc>https://docs.tavily.com/documentation/integrations/nemo-deepagents</loc>
    <lastmod>2026-07-16</lastmod>
  </url>
  <url>
    <loc>https://docs.tavily.com/documentation/integrations/mcp</loc>
    <lastmod>2026-07-10</lastmod>
  </url>
  <url>
    <loc>https://docs.tavily.com/documentation/old-page</loc>
    <lastmod>2025-01-01</lastmod>
  </url>
</urlset>"""


def _mock_get(url, accept="text/html"):
    if "sitemap.xml" in url:
        return (200, _SITEMAP_XML)
    return (404, "")


def test_docs_drilldown_uses_sitemap():
    from services.source_drilldown import drilldown_docs
    with patch("services.source_drilldown._get", side_effect=_mock_get):
        result = drilldown_docs(
            "https://docs.tavily.com",
            "2026-07-08T00:00:00Z",
            "2026-07-21T00:00:00Z",
        )
    assert result.drilldown_status in ("success", "partial")


def test_docs_drilldown_finds_integration_pages():
    from services.source_drilldown import drilldown_docs
    with patch("services.source_drilldown._get", side_effect=_mock_get):
        result = drilldown_docs(
            "https://docs.tavily.com",
            "2026-07-08T00:00:00Z",
            "2026-07-21T00:00:00Z",
        )
    urls = [it.source_url for it in result.discovered_items]
    assert any("nemo" in u or "integration" in u for u in urls)


def test_docs_index_itself_not_imported():
    """docs 首页本身不在 discovered_items 中。"""
    from services.source_drilldown import drilldown_docs
    with patch("services.source_drilldown._get", side_effect=_mock_get):
        result = drilldown_docs(
            "https://docs.tavily.com",
            "2026-07-08T00:00:00Z",
            "2026-07-21T00:00:00Z",
        )
    urls = [it.source_url for it in result.discovered_items]
    assert "https://docs.tavily.com/" not in urls


def test_sitemap_lastmod_marked_inferred():
    """sitemap lastmod 来源标记 discovery_method=sitemap_lastmod。"""
    from services.source_drilldown import drilldown_docs
    with patch("services.source_drilldown._get", side_effect=_mock_get):
        result = drilldown_docs(
            "https://docs.tavily.com",
            "2026-07-08T00:00:00Z",
            "2026-07-21T00:00:00Z",
        )
    for item in result.discovered_items:
        assert item.discovery_method == "sitemap_lastmod"
