"""测试：Nemo Deep Agents 可从完整 sitemap 发现"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from unittest.mock import patch


_SITEMAP_WITH_NEMO = """<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <url>
    <loc>https://docs.tavily.com/changelog</loc>
    <lastmod>2026-07-21T16:51:45.106Z</lastmod>
  </url>
  <url>
    <loc>https://docs.tavily.com/documentation/integrations/nemo-deepagents</loc>
    <lastmod>2026-07-09T17:07:49.892Z</lastmod>
  </url>
  <url>
    <loc>https://docs.tavily.com/documentation/integrations/anthropic</loc>
    <lastmod>2026-05-27T17:59:08.034Z</lastmod>
  </url>
  <url>
    <loc>https://docs.tavily.com/documentation/old-page</loc>
    <lastmod>2025-01-01T00:00:00.000Z</lastmod>
  </url>
</urlset>"""


def _mock_sitemap(url, accept="text/html"):
    if "sitemap" in url:
        return (200, _SITEMAP_WITH_NEMO)
    return (404, "")


def test_nemo_discovered_from_sitemap():
    """Nemo Deep Agents 从完整 sitemap 发现（不硬编码）。"""
    from services.source_drilldown import drilldown_docs
    with patch("services.source_drilldown._get", side_effect=_mock_sitemap):
        result = drilldown_docs(
            "https://docs.tavily.com",
            "2026-07-08T00:00:00Z",
            "2026-07-21T00:00:00Z",
        )
    urls = [it.source_url for it in result.discovered_items]
    assert "https://docs.tavily.com/documentation/integrations/nemo-deepagents" in urls, (
        "Nemo Deep Agents 应从 sitemap 中发现"
    )


def test_nemo_uses_updated_at_not_published_date():
    """Nemo 的 sitemap lastmod 写入 updated_at，不写 published_date。"""
    from services.source_drilldown import drilldown_docs
    with patch("services.source_drilldown._get", side_effect=_mock_sitemap):
        result = drilldown_docs(
            "https://docs.tavily.com",
            "2026-07-08T00:00:00Z",
            "2026-07-21T00:00:00Z",
        )
    nemo = next(
        (it for it in result.discovered_items
         if "nemo-deepagents" in it.source_url),
        None,
    )
    assert nemo is not None
    assert nemo.updated_at != "", "updated_at 应包含 lastmod"
    assert nemo.published_date == "", "published_date 应为空（sitemap 给的是更新时间）"


def test_nemo_within_window():
    """Nemo lastmod=2026-07-09 在 2026-07-08~07-21 窗口内。"""
    from services.source_drilldown import drilldown_docs
    with patch("services.source_drilldown._get", side_effect=_mock_sitemap):
        result = drilldown_docs(
            "https://docs.tavily.com",
            "2026-07-08T00:00:00Z",
            "2026-07-21T00:00:00Z",
        )
    nemo = next((it for it in result.discovered_items if "nemo-deepagents" in it.source_url), None)
    assert nemo is not None
    assert nemo.within_window, f"Nemo 应在窗口内，updated_at={nemo.updated_at}"
