"""测试：Event 下钻"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from unittest.mock import patch
from services.page_type_classifier import classify_page_type


_EVENT_INDEX_HTML = """<html><body>
<a href="/tavily-h550">Dev Cup: Tavily x Composio</a>
<a href="/exa-event">Exa Hackathon</a>
<a href="https://otherdomain.com/event">Unrelated</a>
</body></html>"""


def _mock_luma_get(url, accept="text/html"):
    return (200, _EVENT_INDEX_HTML)


def test_luma_slug_is_event_detail():
    assert classify_page_type("https://luma.com/tavily-h550") == "event_detail"


def test_luma_homepage_is_event_index():
    assert classify_page_type("https://luma.com") == "event_index"


def test_event_drilldown_discovers_details():
    from services.source_drilldown import drilldown_event
    with patch("services.source_drilldown._get", side_effect=_mock_luma_get):
        result = drilldown_event(
            "https://luma.com",
            "2026-07-08T00:00:00Z",
            "2026-07-21T00:00:00Z",
        )
    assert len(result.discovered_items) >= 1
    urls = [it.source_url for it in result.discovered_items]
    assert any("tavily-h550" in u for u in urls)


def test_event_index_not_in_discovered():
    from services.source_drilldown import drilldown_event
    with patch("services.source_drilldown._get", side_effect=_mock_luma_get):
        result = drilldown_event(
            "https://luma.com",
            "2026-07-08T00:00:00Z",
            "2026-07-21T00:00:00Z",
        )
    urls = [it.source_url for it in result.discovered_items]
    assert "https://luma.com" not in urls
