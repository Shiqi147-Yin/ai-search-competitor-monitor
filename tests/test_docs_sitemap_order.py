"""测试：Docs sitemap 先过滤后 limit"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from unittest.mock import patch


def _build_sitemap(entries: list[tuple[str, str]]) -> str:
    items = "\n".join(
        f"<url><loc>{loc}</loc><lastmod>{lm}</lastmod></url>"
        for loc, lm in entries
    )
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
{items}
</urlset>"""


def _mock_sitemap_get(xml_content):
    def _fn(url, accept="text/html"):
        if "sitemap" in url:
            return (200, xml_content)
        return (404, "")
    return _fn


def test_filter_before_limit():
    """先过滤窗口内，再 limit，不漏掉排序靠后的近期页面。"""
    # 构造 25 条旧页面 + 1 条新页面（第 26 位）
    entries = [(f"https://docs.example.com/page-{i}", "2025-01-01") for i in range(25)]
    entries.append(("https://docs.example.com/integration/nemo", "2026-07-15"))

    xml = _build_sitemap(entries)
    from services.source_drilldown import drilldown_docs
    with patch("services.source_drilldown._get", side_effect=_mock_sitemap_get(xml)):
        result = drilldown_docs(
            "https://docs.example.com",
            "2026-07-08T00:00:00Z",
            "2026-07-21T00:00:00Z",
        )

    urls = [it.source_url for it in result.discovered_items]
    assert "https://docs.example.com/integration/nemo" in urls, (
        "窗口内第 26 条页面不应因 limit=20 被丢弃"
    )


def test_window_outside_not_push_inside_out():
    """窗口外页面不能挤掉窗口内页面。"""
    entries = [("https://docs.example.com/integration/recent", "2026-07-15")]
    entries += [(f"https://docs.example.com/old-{i}", "2025-01-01") for i in range(30)]

    xml = _build_sitemap(entries)
    from services.source_drilldown import drilldown_docs
    with patch("services.source_drilldown._get", side_effect=_mock_sitemap_get(xml)):
        result = drilldown_docs(
            "https://docs.example.com",
            "2026-07-08T00:00:00Z",
            "2026-07-21T00:00:00Z",
        )

    within = [it for it in result.discovered_items if it.within_window]
    assert len(within) >= 1
    urls = [it.source_url for it in result.discovered_items]
    assert "https://docs.example.com/integration/recent" in urls
