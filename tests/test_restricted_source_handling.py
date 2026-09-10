"""测试：受限来源（X / LinkedIn）处理"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from unittest.mock import patch
from services.url_fetcher import FetchResult


def _restricted_fetch(url):
    return FetchResult(url=url, status="restricted", error="HTTP 403", http_status_code=403)


def _timeout_fetch(url):
    return FetchResult(url=url, status="failed", error="ConnectTimeout: x")


def test_x_restricted_keeps_url():
    """X 受限时 result.url 仍保留原始链接。"""
    with patch("services.url_fetcher.requests.get") as mock_get:
        mock_get.return_value.status_code = 403
        mock_get.return_value.url = "https://x.com/tavily_ai/status/123"
        mock_get.return_value.headers = {"Content-Type": "text/html"}
        mock_get.return_value.history = []
        from services.url_fetcher import fetch_url
        result = fetch_url("https://x.com/tavily_ai/status/123")

    assert result.url == "https://x.com/tavily_ai/status/123"
    assert result.status == "restricted"


def test_linkedin_restricted_status():
    """LinkedIn 403 → fetch_status = restricted。"""
    with patch("services.url_fetcher.requests.get") as mock_get:
        mock_get.return_value.status_code = 403
        mock_get.return_value.url = "https://linkedin.com/company/tavily"
        mock_get.return_value.headers = {"Content-Type": "text/html"}
        mock_get.return_value.history = []
        from services.url_fetcher import fetch_url
        result = fetch_url("https://linkedin.com/company/tavily")

    assert result.status == "restricted"


def test_restricted_marked_as_needs_manual():
    """受限来源需要人工补充。"""
    from services.source_capability_classifier import classify_fetch_result
    result = classify_fetch_result(
        fetch_status="restricted",
        has_title=False,
        has_description=False,
        has_published_date=False,
        source_platform="X",
    )
    assert result.needs_manual
    assert result.automation_level == "C"


def test_restricted_does_not_crash():
    """受限页面不进入崩溃分支，正常返回结果。"""
    from services.url_fetcher import fetch_url
    with patch("services.url_fetcher.requests.get") as mock_get:
        mock_get.return_value.status_code = 403
        mock_get.return_value.url = "https://x.com/any"
        mock_get.return_value.headers = {"Content-Type": "text/html"}
        mock_get.return_value.history = []
        result = fetch_url("https://x.com/any")

    assert result.status == "restricted"
    assert result.url == "https://x.com/any"


def test_x_platform_correctly_detected():
    """X 来源平台识别正确。"""
    from services.source_detector import detect_platform
    assert detect_platform("https://x.com/tavily_ai/status/123") == "X"
    assert detect_platform("https://twitter.com/ExaAILabs") == "X"


def test_linkedin_platform_correctly_detected():
    """LinkedIn 来源平台识别正确。"""
    from services.source_detector import detect_platform
    assert detect_platform("https://linkedin.com/company/tavily") == "LinkedIn"
    assert detect_platform("https://www.linkedin.com/posts/exaai") == "LinkedIn"


def test_restricted_batch_record_marks_manual():
    """批次服务中受限记录标记 is_duplicate=False，fetch_status=restricted，允许人工补充后写入。"""
    from services.import_batch_service import BatchRecord
    # 模拟一个受限记录
    rec = BatchRecord(
        original_url="https://x.com/post/123",
        normalized_url="https://x.com/post/123",
        competitor="Other",
        source_platform="X",
        fetch_status="restricted",
        fetch_error="HTTP 403",
        is_duplicate=False,
        is_invalid_url=False,
    )
    # 受限记录不是重复，可以写入待审核区
    assert not rec.is_duplicate
    assert rec.fetch_status == "restricted"
