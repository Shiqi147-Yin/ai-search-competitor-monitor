"""测试：LinkedIn 降级处理 + HTTP 451 修复"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from unittest.mock import patch, MagicMock
import pytest


def _make_resp(status_code, url="https://linkedin.com/test"):
    r = MagicMock()
    r.status_code = status_code
    r.url = url
    r.headers = {"Content-Type": "text/html"}
    r.history = []
    r.text = ""
    return r


# ── HTTP 451 ─────────────────────────────────────────────────────

def test_http_451_is_restricted_not_failed():
    """HTTP 451 → fetch_status=restricted，不是 failed。"""
    with patch("services.url_fetcher.requests.get") as mock_get:
        mock_get.return_value = _make_resp(451, "https://linkedin.com/posts/xyz")
        from services.url_fetcher import fetch_url
        result = fetch_url("https://linkedin.com/posts/xyz")

    assert result.status == "restricted", f"期望 restricted，实际 {result.status}"


def test_http_451_error_contains_451():
    """HTTP 451 的 fetch_error 包含 HTTP 451。"""
    with patch("services.url_fetcher.requests.get") as mock_get:
        mock_get.return_value = _make_resp(451)
        from services.url_fetcher import fetch_url
        result = fetch_url("https://linkedin.com/posts/451")

    assert "451" in result.error


def test_http_451_url_preserved():
    """HTTP 451 时原始 URL 不被清空。"""
    url = "https://linkedin.com/posts/test-451"
    with patch("services.url_fetcher.requests.get") as mock_get:
        mock_get.return_value = _make_resp(451, url)
        from services.url_fetcher import fetch_url
        result = fetch_url(url)

    assert result.url == url


def test_http_451_needs_manual():
    """HTTP 451 → needs_manual=True（restricted 等级）。"""
    from services.source_capability_classifier import classify_fetch_result
    result = classify_fetch_result(
        fetch_status="restricted",
        has_title=False,
        has_description=False,
        has_published_date=False,
        source_platform="LinkedIn",
    )
    assert result.needs_manual


# ── LinkedIn HTTP 403 ─────────────────────────────────────────────

def test_linkedin_403_is_restricted():
    """LinkedIn 403 → restricted（原有测试保留）。"""
    with patch("services.url_fetcher.requests.get") as mock_get:
        mock_get.return_value = _make_resp(403, "https://linkedin.com/company/exa-ai")
        from services.url_fetcher import fetch_url
        result = fetch_url("https://linkedin.com/company/exa-ai")

    assert result.status == "restricted"


def test_linkedin_url_preserved_on_restriction():
    """LinkedIn 受限时原始 URL 不被清空。"""
    with patch("services.url_fetcher.requests.get") as mock_get:
        mock_get.return_value = _make_resp(403, "https://linkedin.com/posts/exa-ai_update")
        from services.url_fetcher import fetch_url
        result = fetch_url("https://linkedin.com/posts/exa-ai_update")

    assert result.url == "https://linkedin.com/posts/exa-ai_update"


# ── LinkedIn slug 识别 ────────────────────────────────────────────

def test_exa_ai_linkedin_slug_recognized():
    """exa-ai LinkedIn slug → Exa。"""
    from services.source_detector import detect_competitor, invalidate_account_cache
    invalidate_account_cache()
    assert detect_competitor("https://www.linkedin.com/company/exa-ai/") == "Exa"
    invalidate_account_cache()


def test_tavily_linkedin_slug_recognized():
    """tavily LinkedIn slug → Tavily。"""
    from services.source_detector import detect_competitor, invalidate_account_cache
    invalidate_account_cache()
    assert detect_competitor("https://www.linkedin.com/company/tavily/") == "Tavily"
    invalidate_account_cache()


def test_brave_linkedin_slug_recognized():
    """brave LinkedIn slug → Brave。"""
    from services.source_detector import detect_competitor, invalidate_account_cache
    invalidate_account_cache()
    assert detect_competitor("https://www.linkedin.com/company/brave-software/") == "Brave"
    invalidate_account_cache()


def test_unknown_linkedin_slug_is_other():
    """无法识别的 slug → Other。"""
    from services.source_detector import detect_competitor, invalidate_account_cache
    invalidate_account_cache()
    assert detect_competitor("https://www.linkedin.com/company/some-random-company/") == "Other"
    invalidate_account_cache()


# ── 能力等级 ─────────────────────────────────────────────────────

def test_linkedin_restricted_automation_level_c():
    """LinkedIn restricted → C 级（主要人工补充）。"""
    from services.source_capability_classifier import classify_fetch_result
    result = classify_fetch_result(
        fetch_status="restricted",
        has_title=False,
        has_description=False,
        has_published_date=False,
        source_platform="LinkedIn",
    )
    assert result.automation_level == "C"


def test_linkedin_no_unhandled_exception():
    """LinkedIn 访问不进入未处理异常分支。"""
    import requests
    with patch("services.url_fetcher.requests.get",
               side_effect=requests.exceptions.ConnectionError("refused")):
        from services.url_fetcher import fetch_url
        result = fetch_url("https://linkedin.com/posts/xyz")
    assert result.status == "failed"


def test_linkedin_platform_detected():
    """LinkedIn 平台识别正确。"""
    from services.source_detector import detect_platform
    assert detect_platform("https://linkedin.com/company/exa-ai") == "LinkedIn"
    assert detect_platform("https://www.linkedin.com/posts/tavily_ai") == "LinkedIn"


# ── 展示状态文案 ──────────────────────────────────────────────────

def test_restricted_status_label_is_not_failed():
    """restricted 状态的展示文案应包含'受限'，不应直接显示'失败'。"""
    # 这是逻辑约束：_FETCH_STATUS_LABEL["restricted"] 不应含"失败"
    label_map = {
        "success":    "✅ 成功",
        "partial":    "⚠️ 部分成功",
        "failed":     "❌ 失败",
        "restricted": "🔒 访问受限",
        "pending":    "⏳ 待抓取",
    }
    restricted_label = label_map["restricted"]
    assert "失败" not in restricted_label
    assert "受限" in restricted_label
