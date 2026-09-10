"""测试：LinkedIn HTTP 451 受限记录置信度"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from services.content_analyzer import analyze_record


def _linkedin_451(source_url="https://linkedin.com/posts/exa-ai_raise-summit",
                  title="", summary="", raw_content="", **kwargs):
    base = {
        "competitor": "Exa", "source_platform": "LinkedIn",
        "title": title, "summary": summary, "raw_content": raw_content,
        "fetch_status": "restricted", "fetch_error": "HTTP 451",
        "source_url": source_url,
        "capability_change": 0, "integration_change": 0,
        "docs_changed": 0, "developer_experience_change": 0, "change_summary": "",
    }
    base.update(kwargs)
    return base


def test_linkedin_451_no_content_confidence_below_35():
    """LinkedIn HTTP 451 + 无正文 → confidence <= 0.35。"""
    rec = _linkedin_451()
    result = analyze_record(rec)
    assert result.analysis_confidence <= 0.35, (
        f"置信度 {result.analysis_confidence} 超过 0.35"
    )


def test_linkedin_451_evidence_source_is_url_slug():
    """LinkedIn HTTP 451 无正文时 evidence_source = url_slug_only。"""
    rec = _linkedin_451()
    result = analyze_record(rec)
    assert result.evidence_source == "url_slug_only"


def test_linkedin_451_analysis_status_is_partial():
    """LinkedIn HTTP 451 → analysis_status = partial。"""
    rec = _linkedin_451()
    result = analyze_record(rec)
    assert result.analysis_status == "partial"


def test_linkedin_451_reason_mentions_restriction():
    """analysis_reason 包含访问受限和需人工确认。"""
    rec = _linkedin_451()
    result = analyze_record(rec)
    reason = result.analysis_reason
    assert any(kw in reason for kw in ["受限", "451", "人工确认"])


def test_linkedin_451_confidence_never_100():
    """LinkedIn HTTP 451 不得出现 1.0 置信度。"""
    rec = _linkedin_451()
    result = analyze_record(rec)
    assert result.analysis_confidence < 1.0


def test_linkedin_451_with_manual_summary_can_exceed_restricted_floor():
    """有人工摘要时，置信度仍受 restricted 上限（0.40）约束，但可高于无内容时。"""
    rec = _linkedin_451(
        summary="Exa participating in RAISE Summit 2026 developer event.",
    )
    result = analyze_record(rec)
    # 有摘要 → 可高于纯 slug 的 0.2，但仍 <= 0.40
    assert result.analysis_confidence <= 0.40
