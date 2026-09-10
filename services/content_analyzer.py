"""自动预分析服务（v3：分层置信度 + fetch_status 绝对上限 + evidence_source）"""
import json
from dataclasses import dataclass, field
from typing import Optional

from services.classification_rules import (
    CATEGORY_KEYWORDS,
    SECONDARY_TAG_HINTS,
    HIGH_PRIORITY_KEYWORDS,
    LOW_PRIORITY_KEYWORDS,
    BUSINESS_VALUE_TEMPLATES,
    SUGGESTED_ACTION_TEMPLATES,
    GAP_ANALYSIS_TEMPLATES,
    STRONG_PRODUCT_SIGNALS,
    STRONG_ECOSYSTEM_SIGNALS,
    STRONG_MARKET_SIGNALS,
)

_PROTECTED_ANALYSIS_FIELDS = {
    "category", "business_value", "priority", "suggested_action",
    "gap_analysis", "querit_status",
}

# fetch_status → 置信度绝对上限（无论内容多丰富都不超过此值）
_FETCH_STATUS_CAPS = {
    "success":    1.00,
    "partial":    0.70,
    "restricted": 0.40,
    "failed":     0.25,
    "pending":    0.55,
    "":           0.55,
}


def _evidence_source(title: str, summary: str, raw_content: str) -> str:
    """full_content / title_and_summary / title_only / url_slug_only / no_content"""
    is_title_url = title.startswith("http://") or title.startswith("https://")
    has_content = bool(raw_content and len(raw_content.strip()) > 50)
    has_summary = bool(summary and len(summary.strip()) > 10)
    has_title = bool(title and len(title.strip()) > 5) and not is_title_url

    if has_content and has_title:
        return "full_content"
    if has_summary and has_title:
        return "title_and_summary"
    if has_title:
        return "title_only"
    if summary or raw_content:
        return "title_only"
    return "url_slug_only"


def _content_richness(title: str, summary: str, raw_content: str) -> tuple[int, float]:
    """返回 (richness_level 1-4, content_based_cap)。
    fetch_status 上限由调用方单独应用（两者取 min）。
    """
    is_title_url = title.startswith("http://") or title.startswith("https://")
    has_content = bool(raw_content and len(raw_content.strip()) > 50)
    has_summary = bool(summary and len(summary.strip()) > 10)
    has_title = bool(title and len(title.strip()) > 5) and not is_title_url

    if has_content and has_title:
        return 4, 0.95
    if has_summary and has_title:
        return 3, 0.79
    if has_title:
        return 2, 0.59
    return 1, 0.39


@dataclass
class AnalysisResult:
    category: str = "待评估"
    secondary_tags: list = field(default_factory=list)
    business_value: str = ""
    priority: str = "中"
    suggested_action: str = ""
    querit_status: str = "待评估"
    gap_analysis: str = ""
    analysis_status: str = "partial"
    analysis_confidence: float = 0.0
    analysis_reason: str = ""
    evidence_source: str = "no_content"
    auto_category: str = "待评估"
    auto_business_value: str = ""
    auto_priority: str = "中"
    auto_suggested_action: str = ""
    auto_querit_status: str = "待评估"
    auto_gap_analysis: str = ""

    def to_db_fields(self) -> dict:
        return {
            "auto_category": self.auto_category,
            "auto_business_value": self.auto_business_value,
            "auto_priority": self.auto_priority,
            "auto_suggested_action": self.auto_suggested_action,
            "auto_querit_status": self.auto_querit_status,
            "auto_gap_analysis": self.auto_gap_analysis,
            "secondary_tags": json.dumps(self.secondary_tags, ensure_ascii=False),
            "analysis_status": self.analysis_status,
            "analysis_confidence": self.analysis_confidence,
            "analysis_reason": self.analysis_reason,
            "analyzed_at": _now_iso(),
        }

    def to_fill_fields(self, existing: dict) -> dict:
        result: dict = {}
        mapping = {
            "category": self.auto_category,
            "business_value": self.auto_business_value,
            "priority": self.auto_priority,
            "suggested_action": self.auto_suggested_action,
            "querit_status": self.auto_querit_status,
            "gap_analysis": self.auto_gap_analysis,
        }
        for key, auto_val in mapping.items():
            if _is_empty_or_default(key, existing.get(key)) and auto_val:
                result[key] = auto_val
        result.update(self.to_db_fields())
        return result


def _now_iso() -> str:
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoformat()


def _is_empty_or_default(key: str, val) -> bool:
    if val is None or str(val).strip() == "":
        return True
    return val in {"待评估": {"待评估"}, "querit_status": {"待评估"}}.get(key, set())


# ── 主分析入口 ────────────────────────────────────────────────

def analyze_record(record: dict) -> AnalysisResult:
    try:
        return _do_analyze(record)
    except Exception as e:
        return AnalysisResult(
            category="待评估",
            analysis_status="failed",
            analysis_reason=f"分析异常：{type(e).__name__}: {str(e)[:80]}",
            analysis_confidence=0.0,
            auto_category="待评估",
        )


def _do_analyze(record: dict) -> AnalysisResult:
    competitor = (record.get("competitor") or "").strip()
    platform = (record.get("source_platform") or "").strip()
    title = (record.get("title") or record.get("raw_title") or "").strip()
    summary = (record.get("summary") or record.get("description") or "").strip()
    raw_content = (record.get("raw_content") or "").strip()
    manual_note = (record.get("manual_note") or "").strip()
    change_summary = (record.get("change_summary") or "").strip()
    fetch_status = (record.get("fetch_status") or "").strip()
    source_url = record.get("source_url") or ""
    fetch_error = (record.get("fetch_error") or "").lower()

    docs_changed = bool(record.get("docs_changed"))
    capability_change = bool(record.get("capability_change"))
    integration_change = bool(record.get("integration_change"))
    developer_experience_change = bool(record.get("developer_experience_change"))

    combined = " ".join([
        title, summary, raw_content[:1000], manual_note,
        change_summary, source_url,
    ]).lower()

    # ── 内容充足性 & 证据来源 ────────────────────────────────
    richness, content_cap = _content_richness(title, summary, raw_content)
    evid = _evidence_source(title, summary, raw_content)
    # fetch_status 绝对上限
    status_cap = _FETCH_STATUS_CAPS.get(fetch_status, 0.55)
    # 最终置信度上限 = min(内容基础上限, fetch_status 上限)
    confidence_cap = round(min(content_cap, status_cap), 2)

    # ── LinkedIn HTTP 451 专项 ───────────────────────────────
    is_linkedin_451 = (
        platform == "LinkedIn" and
        fetch_status == "restricted" and
        "451" in fetch_error and
        richness <= 1
    )
    if is_linkedin_451:
        slug_cat = _guess_from_url(source_url)
        category = slug_cat or "待评估"
        reason = (
            "LinkedIn 页面访问受限（HTTP 451），未获取正文，"
            "当前仅根据 URL slug 中的关键词进行初步判断，需人工确认。"
        )
        bv = _generate_business_value(category, None, competitor, title)
        sa = SUGGESTED_ACTION_TEMPLATES.get((category, None), "需人工补充内容后重新分析。")
        return AnalysisResult(
            category=category,
            auto_category=category,
            analysis_status="partial",
            analysis_confidence=min(0.2, confidence_cap),
            analysis_reason=reason,
            evidence_source="url_slug_only",
            auto_querit_status="待评估",
            auto_priority="低",
            auto_business_value=bv,
            auto_suggested_action=sa,
            auto_gap_analysis=GAP_ANALYSIS_TEMPLATES[None],
        )

    # ── restricted / failed 且无内容 ─────────────────────────
    if fetch_status in ("restricted", "failed") and richness <= 1:
        reason = (
            f"页面访问受限（{fetch_status}），当前主要根据 URL slug "
            f"中的关键词进行初步判断，置信度较低，需人工确认。"
        )
        slug_cat = _guess_from_url(source_url)
        if slug_cat:
            return AnalysisResult(
                category=slug_cat,
                auto_category=slug_cat,
                analysis_status="partial",
                analysis_confidence=min(0.2, confidence_cap),
                analysis_reason=reason,
                evidence_source="url_slug_only",
                auto_querit_status="待评估",
                auto_priority="低",
                auto_business_value=_generate_business_value(slug_cat, None, competitor, title),
                auto_suggested_action=SUGGESTED_ACTION_TEMPLATES.get((slug_cat, None), ""),
                auto_gap_analysis=GAP_ANALYSIS_TEMPLATES[None],
            )
        return AnalysisResult(
            category="待评估",
            auto_category="待评估",
            analysis_status="partial",
            analysis_confidence=min(0.1, confidence_cap),
            analysis_reason="内容不足且访问受限，无法完成分类，归为待评估。",
            evidence_source="no_content",
        )

    # 无任何内容
    has_content = bool(title or summary or raw_content)
    if not has_content and platform not in ("GitHub",):
        return AnalysisResult(
            category="待评估",
            auto_category="待评估",
            analysis_status="partial",
            analysis_reason="内容不足：无标题、摘要或正文，无法完成分类",
            analysis_confidence=min(0.1, confidence_cap),
            evidence_source="no_content",
            auto_querit_status="待评估",
            auto_priority="中",
        )

    # ── 强信号检测（直接决定分类）────────────────────────────
    strong_product = any(sig in combined for sig in STRONG_PRODUCT_SIGNALS)
    strong_eco = any(sig in combined for sig in STRONG_ECOSYSTEM_SIGNALS)
    strong_market = any(sig in combined for sig in STRONG_MARKET_SIGNALS)

    # GitHub 专项加分
    scores = {cat: 0 for cat in CATEGORY_KEYWORDS}
    if capability_change:
        scores["产品与功能"] += 3
    if integration_change:
        scores["生态与集成"] += 3
    if developer_experience_change:
        scores["产品与功能"] += 1
    if docs_changed and not capability_change and not integration_change:
        scores["产品与功能"] += 1

    if platform == "Event":
        scores["市场与运营"] += 3

    for cat, keywords in CATEGORY_KEYWORDS.items():
        for kw in keywords:
            if kw in combined:
                scores[cat] += 1

    # ── 确定一级分类 ──────────────────────────────────────
    if strong_product and not strong_eco:
        category = "产品与功能"
        # 强信号基础分，再受 confidence_cap 约束
        base_confidence = 0.88 + scores["产品与功能"] * 0.02
        reason = f"强信号：产品能力关键词命中（{[s for s in STRONG_PRODUCT_SIGNALS if s in combined][:3]}）"
    elif strong_eco and not strong_product:
        category = "生态与集成"
        base_confidence = 0.82 + scores["生态与集成"] * 0.02
        reason = f"强信号：生态集成关键词命中（{[s for s in STRONG_ECOSYSTEM_SIGNALS if s in combined][:3]}）"
    elif strong_product and strong_eco:
        category = "产品与功能"
        base_confidence = 0.82
        reason = "产品与生态均有强信号，优先产品与功能（含生态分发）"
    elif strong_market:
        category = "市场与运营"
        base_confidence = 0.55  # 市场信号基础分不超过 0.55
        reason = "强信号：活动或传播关键词命中"
    else:
        max_score = max(scores.values())
        if max_score == 0:
            category = "待评估"
            base_confidence = 0.15
            reason = "未匹配到任何分类关键词，归为待评估"
        else:
            priority_order = ["产品与功能", "生态与集成", "市场与运营"]
            top_cats = [c for c in priority_order if scores[c] == max_score]
            category = top_cats[0] if top_cats else max(scores, key=lambda k: scores[k])
            total = sum(scores.values())
            ratio = scores[category] / max(total, 1)
            # 基础分 = 得分比例 * 内容上限的 70% + 基础 0.3（最大 content_cap 的 90%）
            base_confidence = round(min(ratio * 0.7 + 0.3, content_cap * 0.9), 2)
            reason = (
                f"关键词得分：{dict(scores)}，"
                f"选择'{category}'（得分 {scores[category]}，比例 {ratio:.0%}）"
            )

    # ── 最终置信度 = min(基础分, 内容上限, fetch_status 上限) ──────
    confidence = round(min(base_confidence, content_cap, status_cap), 2)

    if richness <= 1:
        # 仅 URL slug 级别，确保不超过 0.39
        confidence = min(confidence, 0.39)
        analysis_status = "partial"
    elif richness == 2:
        analysis_status = "partial" if confidence < 0.5 else "analyzed"
    else:
        analysis_status = "analyzed" if confidence >= 0.5 else "partial"

    # ── secondary_tags ────────────────────────────────────────
    secondary_tags = _extract_secondary_tags(combined, category)

    # ── 优先级 ────────────────────────────────────────────────
    priority = _determine_priority(combined, category, capability_change, integration_change)

    # ── 场景关键词 ──────────────────────────────────────────
    scene_key = _detect_scene_key(combined)

    # ── 生成文本字段 ──────────────────────────────────────────
    business_value = _generate_business_value(category, scene_key, competitor, title)
    suggested_action = _generate_suggested_action(category, scene_key, priority)
    gap_analysis = _generate_gap_analysis(scene_key)

    return AnalysisResult(
        category=category,
        secondary_tags=secondary_tags,
        business_value=business_value,
        priority=priority,
        suggested_action=suggested_action,
        querit_status="待评估",
        gap_analysis=gap_analysis,
        analysis_status=analysis_status,
        analysis_confidence=confidence,
        analysis_reason=reason,
        evidence_source=evid,
        auto_category=category,
        auto_business_value=business_value,
        auto_priority=priority,
        auto_suggested_action=suggested_action,
        auto_querit_status="待评估",
        auto_gap_analysis=gap_analysis,
    )


def _guess_from_url(url: str) -> Optional[str]:
    """从 URL slug 猜测分类（低置信度）。"""
    url_lower = url.lower()
    market_hints = ["summit", "event", "conference", "hackathon", "webinar",
                    "meetup", "raise", "camp", "dev-cup", "community"]
    eco_hints = ["integration", "connector", "plugin"]
    product_hints = ["api", "release", "sdk", "changelog"]
    if any(h in url_lower for h in market_hints):
        return "市场与运营"
    if any(h in url_lower for h in eco_hints):
        return "生态与集成"
    if any(h in url_lower for h in product_hints):
        return "产品与功能"
    return None


def _extract_secondary_tags(combined: str, primary_category: str) -> list[str]:
    tags = []
    for tag, hints in SECONDARY_TAG_HINTS.items():
        if any(h in combined for h in hints):
            tags.append(tag)
    if primary_category == "产品与功能" and any(
        kw in combined for kw in CATEGORY_KEYWORDS["生态与集成"]
    ):
        if "生态分发" not in tags:
            tags.append("生态分发")
    if primary_category == "生态与集成" and any(
        kw in combined for kw in CATEGORY_KEYWORDS["产品与功能"]
    ):
        if "产品能力" not in tags:
            tags.append("产品能力")
    return list(dict.fromkeys(tags))[:6]


def _determine_priority(combined: str, category: str, cap_change: bool, int_change: bool) -> str:
    if any(kw in combined for kw in HIGH_PRIORITY_KEYWORDS):
        return "高"
    if any(kw in combined for kw in LOW_PRIORITY_KEYWORDS):
        return "低"
    if category == "产品与功能" and cap_change:
        return "高"
    if category == "生态与集成" and int_change:
        return "中"
    if category == "市场与运营":
        return "低"
    return "中"


def _detect_scene_key(combined: str) -> Optional[str]:
    scene_priority = [
        "agent skills", "skills add", "npx skills",
        "pricing", "streaming", "mcp",
        "place search", "cerebras", "langchain", "kiro",
        "coding agent", "integration",
    ]
    for key in scene_priority:
        if key in combined:
            return key
    return None


def _generate_business_value(category: str, scene_key: Optional[str],
                              competitor: str, title: str) -> str:
    if scene_key:
        val = BUSINESS_VALUE_TEMPLATES.get((category, scene_key))
        if val:
            return val
    val = BUSINESS_VALUE_TEMPLATES.get((category, None))
    if val:
        return val
    cat_desc = {
        "产品与功能": "竞品产品能力更新，可能影响 Querit 的产品竞争力，需评估差距。",
        "生态与集成": "竞品生态覆盖面扩大，需评估对 Querit 生态策略的影响。",
        "市场与运营": "通过活动或内容提升竞品品牌认知度，可能影响开发者市场心智。",
        "待评估": "内容信息不足，业务价值待人工补充分析。",
    }
    return cat_desc.get(category, "待人工补充业务意义分析。")


def _generate_suggested_action(category: str, scene_key: Optional[str], priority: str) -> str:
    if scene_key:
        val = SUGGESTED_ACTION_TEMPLATES.get((category, scene_key))
        if val:
            return val
    val = SUGGESTED_ACTION_TEMPLATES.get((category, None))
    if val:
        return val
    return "评估该动态对 Querit 的影响，记录差距并确认跟进方向。"


def _generate_gap_analysis(scene_key: Optional[str]) -> str:
    if scene_key:
        val = GAP_ANALYSIS_TEMPLATES.get(scene_key)
        if val:
            return val
    return GAP_ANALYSIS_TEMPLATES[None]


# ── 辅助：表单默认值选取（供待审核区页面使用）──────────────────

def form_default(rec: dict, human_field: str, auto_field: str,
                 fallback: str = "", default_ignore: set = None) -> str:
    """按优先级返回表单默认值：人工值 > 自动建议 > fallback。"""
    if default_ignore is None:
        default_ignore = {"待评估", ""}
    v = rec.get(human_field)
    if v and str(v).strip() and str(v).strip() not in default_ignore:
        return str(v)
    av = rec.get(auto_field)
    if av and str(av).strip() and str(av).strip() not in default_ignore:
        return str(av)
    return fallback


def form_source_hint(rec: dict, human_field: str, auto_field: str,
                     default_ignore: set = None) -> str:
    """返回字段来源提示文字。"""
    if default_ignore is None:
        default_ignore = {"待评估", ""}
    v = rec.get(human_field)
    has_human = bool(v and str(v).strip() and str(v).strip() not in default_ignore)
    av = rec.get(auto_field)
    has_auto = bool(av and str(av).strip() and str(av).strip() not in default_ignore)

    if has_human:
        return "已使用人工修改结果"
    if has_auto:
        auto_val = str(av).strip()
        return f"系统建议：{auto_val}（已按系统建议预填，可修改）"
    return "信息不足，建议人工判断"
