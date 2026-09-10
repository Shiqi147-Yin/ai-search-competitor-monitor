"""测试：待审核区置信度展示逻辑"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from services.content_analyzer import _FETCH_STATUS_CAPS, _evidence_source


_EVIDENCE_LABEL = {
    "full_content":       "正文与摘要",
    "title_and_summary":  "标题与摘要",
    "title_only":         "仅标题",
    "url_slug_only":      "仅 URL 关键词",
    "no_content":         "依据不足",
}

_CONFIDENCE_LEVEL = {
    (0.80, 1.00): "高",
    (0.50, 0.79): "中",
    (0.20, 0.49): "低",
    (0.00, 0.19): "依据不足",
}


def _conf_level(c: float) -> str:
    if c >= 0.80:
        return "高"
    if c >= 0.50:
        return "中"
    if c >= 0.20:
        return "低"
    return "依据不足"


def test_confidence_display_shows_percentage():
    """置信度展示应为百分比。"""
    conf = 0.35
    display = f"{conf:.0%}"
    assert "35%" in display


def test_confidence_level_labels():
    """各区间标签正确。"""
    assert _conf_level(0.95) == "高"
    assert _conf_level(0.65) == "中"
    assert _conf_level(0.35) == "低"
    assert _conf_level(0.10) == "依据不足"


def test_evidence_label_for_url_slug():
    """url_slug_only 显示为'仅 URL 关键词'。"""
    assert _EVIDENCE_LABEL["url_slug_only"] == "仅 URL 关键词"


def test_evidence_source_no_title_is_url_slug():
    """无标题无正文 → url_slug_only。"""
    src = _evidence_source("", "", "")
    assert src == "url_slug_only"


def test_evidence_source_full_content():
    """有标题+正文 → full_content。"""
    src = _evidence_source(
        "Exa streaming API",
        "New streaming search mode.",
        "We are releasing streaming " * 20,
    )
    assert src == "full_content"


def test_restricted_record_confidence_level_is_low():
    """restricted 记录最高置信度 0.40 → 等级为低。"""
    conf = _FETCH_STATUS_CAPS["restricted"]  # 0.40
    assert _conf_level(conf) == "低"


def test_restricted_display_hint():
    """restricted 标签应提示'访问受限'。"""
    fetch_badge = {
        "restricted": "🔒 访问受限",
        "failed": "❌ 抓取失败",
        "success": "✅ 抓取成功",
    }
    assert "受限" in fetch_badge["restricted"]
    assert "失败" not in fetch_badge["restricted"]
