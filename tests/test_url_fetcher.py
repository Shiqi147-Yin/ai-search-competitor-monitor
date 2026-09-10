"""测试：网页抓取（修订版，使用 mock，不依赖真实网络）"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from unittest.mock import patch, MagicMock

from services.url_fetcher import fetch_url, FetchResult


def _make_response(status_code=200, text="", url="https://example.com/page", content_type="text/html; charset=utf-8"):
    mock_resp = MagicMock()
    mock_resp.status_code = status_code
    mock_resp.text = text
    mock_resp.url = url
    mock_resp.headers = {"Content-Type": content_type}
    mock_resp.history = []
    return mock_resp


_HTML_WITH_TITLE = """<!DOCTYPE html>
<html><head>
  <title>Tavily Launches Streaming API</title>
  <meta property="og:title" content="Tavily Launches Streaming API" />
  <meta property="og:description" content="Real-time streaming search results now available." />
  <meta property="article:published_time" content="2026-07-15T10:00:00Z" />
</head><body><p>Content.</p></body></html>"""

_HTML_NO_TITLE = """<!DOCTYPE html>
<html><head></head><body><p>Some content without title tag.</p></body></html>"""

_HTML_JSONLD = """<!DOCTYPE html>
<html><head><title>Blog Post</title>
  <script type="application/ld+json">
  {"@type": "BlogPosting", "datePublished": "2026-06-01", "headline": "New SDK Release"}
  </script>
</head><body><p>Content.</p></body></html>"""

_HTML_LONG = "<html><head><title>Long</title></head><body>" + ("word " * 2000) + "</body></html>"


@patch("services.url_fetcher.requests.get")
def test_http200_with_title_is_success(mock_get):
    """HTTP 200 + 有标题 → success"""
    mock_get.return_value = _make_response(200, _HTML_WITH_TITLE)
    result = fetch_url("https://example.com/page")
    assert result.status == "success"
    assert result.title != ""
    assert result.http_status_code == 200


@patch("services.url_fetcher.requests.get")
def test_http200_no_title_is_partial_not_failed(mock_get):
    """HTTP 200 + 无标题 → partial（不是 failed）"""
    mock_get.return_value = _make_response(200, _HTML_NO_TITLE)
    result = fetch_url("https://example.com/notitle")
    assert result.status == "partial"
    assert result.status != "failed"
    assert "No title" in result.error


@patch("services.url_fetcher.requests.get")
def test_http403_is_restricted(mock_get):
    """HTTP 403 → restricted"""
    mock_get.return_value = _make_response(403, "")
    result = fetch_url("https://x.com/post/123")
    assert result.status == "restricted"
    assert "403" in result.error


@patch("services.url_fetcher.requests.get")
def test_http429_is_restricted(mock_get):
    """HTTP 429 → restricted"""
    mock_get.return_value = _make_response(429, "")
    result = fetch_url("https://linkedin.com/post")
    assert result.status == "restricted"
    assert "429" in result.error


@patch("services.url_fetcher.requests.get")
def test_connect_timeout_is_failed_with_label(mock_get):
    """ConnectTimeout → failed，error 含 ConnectTimeout"""
    import requests as req_lib
    mock_get.side_effect = req_lib.exceptions.ConnectTimeout()
    result = fetch_url("https://example.com/timeout")
    assert result.status == "failed"
    assert "ConnectTimeout" in result.error


@patch("services.url_fetcher.requests.get")
def test_read_timeout_is_failed_with_label(mock_get):
    """ReadTimeout → failed，error 含 ReadTimeout"""
    import requests as req_lib
    mock_get.side_effect = req_lib.exceptions.ReadTimeout()
    result = fetch_url("https://example.com/slow")
    assert result.status == "failed"
    assert "ReadTimeout" in result.error


@patch("services.url_fetcher.requests.get")
def test_ssl_error_is_failed_with_label(mock_get):
    """SSLError → failed，error 含 SSLError"""
    import requests as req_lib
    mock_get.side_effect = req_lib.exceptions.SSLError("cert verify failed")
    result = fetch_url("https://badssl.example.com")
    assert result.status == "failed"
    assert "SSLError" in result.error


@patch("services.url_fetcher.requests.get")
def test_html_parse_exception_preserved(mock_get):
    """HTML 解析异常 → failed，error 保留具体异常信息。
    通过让 BeautifulSoup 解析引发异常来模拟。
    """
    from unittest.mock import patch as inner_patch
    mock_resp = _make_response(200, "valid html", "https://example.com/broken")
    mock_get.return_value = mock_resp

    with inner_patch("services.url_fetcher.BeautifulSoup",
                     side_effect=Exception("decode error XYZ")):
        result = fetch_url("https://example.com/broken")

    assert result.status == "failed"
    assert "HTML parse error" in result.error or "decode error" in result.error


@patch("services.url_fetcher.requests.get")
def test_original_url_preserved_on_failure(mock_get):
    """失败时原始 URL 仍保留在 result.url。"""
    import requests as req_lib
    mock_get.side_effect = req_lib.exceptions.ConnectionError("refused")
    result = fetch_url("https://example.com/fail")
    assert result.url == "https://example.com/fail"
    assert result.status == "failed"


@patch("services.url_fetcher.requests.get")
def test_content_snippet_length_limited(mock_get):
    """正文片段长度不超过 2000 字符。"""
    mock_get.return_value = _make_response(200, _HTML_LONG)
    result = fetch_url("https://example.com/long")
    assert len(result.content_snippet) <= 2000


@patch("services.url_fetcher.requests.get")
def test_jsonld_date_recognized(mock_get):
    """JSON-LD datePublished 能被识别。"""
    mock_get.return_value = _make_response(200, _HTML_JSONLD)
    result = fetch_url("https://example.com/blog")
    assert "2026" in result.published_date
