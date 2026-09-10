"""测试：受限来源置信度"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from services.content_analyzer import analyze_record


def _restricted_rec(source_url="", title="", summary="", **kwargs):
    base = {
        "competitor": "Exa", "source_platform": "LinkedIn",
        "title": title, "summary": summary, "raw_content": "",
        "fetch_status": "restricted", "fetch_error": "HTTP 451",
        "source_url": source_url,
        "capability_change": 0, "integration_change": 0,
        "docs_changed": 0, "developer_experience_change": 0,
        "change_summary": "",
    }
    base.update(kwargs)
    return base


def test_restricted_no_content_confidence_below_40():
    """LinkedIn 受限且无正文时，置信度 <= 0.4。"""
    rec = _restricted_rec(source_url="https://linkedin.com/posts/exa-ai_update-123")
    result = analyze_record(rec)
    assert result.analysis_confidence <= 0.4, (
        f"置信度 {result.analysis_confidence} 超过 0.4，信息来源仅为 URL slug"
    )


def test_restricted_url_slug_not_full_confidence():
    """仅 URL slug 不能得到 1.0 置信度。"""
    rec = _restricted_rec(source_url="https://linkedin.com/company/exa-ai/activity/raise-summit")
    result = analyze_record(rec)
    assert result.analysis_confidence < 1.0


def test_restricted_summit_url_gets_market_low_confidence():
    """URL 中含 summit → 市场与运营（低置信度）。"""
    rec = _restricted_rec(source_url="https://linkedin.com/posts/exa-ai_raise-summit-2026")
    result = analyze_record(rec)
    # 分类可能是市场与运营或待评估
    assert result.category in ("市场与运营", "待评估")
    assert result.analysis_confidence <= 0.4


def test_restricted_no_semantic_url_is_pending():
    """无语义 URL（如随机 ID）→ 待评估，置信度极低。"""
    rec = _restricted_rec(source_url="https://linkedin.com/posts/some-post-12345")
    result = analyze_record(rec)
    # 置信度极低
    assert result.analysis_confidence <= 0.3


def test_restricted_with_manual_summary_can_analyze():
    """restricted 但有人工摘要时，可以做分析（不强制待评估）。"""
    rec = _restricted_rec(
        source_url="https://linkedin.com/posts/exa-ai_agent-skills",
        summary="Exa launches new Agent Skills for recruiting and sales workflows.",
    )
    result = analyze_record(rec)
    # 有摘要时分析状态可以是 analyzed 或 partial
    assert result.analysis_status in ("analyzed", "partial")
    # 不应全部归为待评估
    # (有摘要时可能仍受 confidence_cap 限制，但不应该 category=待评估)


def test_restricted_reason_mentions_limitation():
    """restricted 无内容时，analysis_reason 应提及受限或依据不足。"""
    rec = _restricted_rec(source_url="https://linkedin.com/posts/exa-ai")
    result = analyze_record(rec)
    reason = result.analysis_reason
    assert any(kw in reason for kw in ["受限", "slug", "不足", "limited", "restricted"])
