"""竞品结果相关性分级服务
判断每条结果的来源权威性和目标匹配程度。
"""
from pathlib import Path
from urllib.parse import urlparse
from typing import Optional
import yaml


_SOURCES_PATH = Path(__file__).parent.parent / "config" / "competitor_sources.yaml"


def _load_sources(competitor: str) -> dict:
    try:
        with open(_SOURCES_PATH, encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
        return data.get(competitor, {})
    except Exception:
        return {}


def _netloc(url: str) -> str:
    try:
        n = urlparse(url).netloc.lower()
        return n.lstrip("www.")
    except Exception:
        return ""


def classify_source_authority(url: str, competitor: str) -> tuple[str, bool]:
    """
    Returns (source_authority, official_source).
    source_authority: official | first_party_ecosystem | reputable_third_party | unknown | low_value_aggregator
    """
    sources = _load_sources(competitor)
    netloc = _netloc(url)

    # Official domains
    official_domains = [d.lstrip("www.") for d in sources.get("official_domains", [])]
    if any(d in netloc for d in official_domains):
        return "official", True

    # Official GitHub
    gh_owners = sources.get("official_github", {}).get("owners", [])
    if "github.com" in netloc:
        path = urlparse(url).path.lower()
        if any(f"/{owner}/" in path or path.startswith(f"/{owner}") for owner in gh_owners):
            return "official", True
        # Generic GitHub (e.g. Topics pages, third-party repos)
        return "reputable_third_party", False

    # Event domains (first-party ecosystem if competitor name in path/title)
    event_domains = sources.get("event_domains", [])
    if any(d in netloc for d in event_domains):
        return "first_party_ecosystem", False

    # Partner domains
    partner_domains = sources.get("partner_domains", [])
    if any(d in netloc for d in partner_domains):
        return "first_party_ecosystem", False

    # Excluded / low-value aggregators
    excluded = sources.get("excluded_domains", [])
    if any(d in netloc for d in excluded):
        return "low_value_aggregator", False

    # Default
    return "unknown", False


_TARGET_MATCH_WEIGHTS = {
    "exact_url": 1.0,
    "domain_keyword": 0.8,
    "title_keyword": 0.65,
    "no_match": 0.0,
}


def classify_relevance(
    result: dict,
    competitor: str,
    match_type: str = "no_match",
    match_score: float = 0.0,
) -> dict:
    """
    返回相关性分级字段。

    target_match_status: exact_target | likely_target | third_party_relevant | weak_match | unrelated
    """
    url = result.get("source_url") or result.get("url") or ""
    authority, official = classify_source_authority(url, competitor)

    # target_match_status
    if match_type == "exact_url":
        target_match = "exact_target"
    elif match_type == "domain_keyword" and official:
        target_match = "likely_target" if match_score >= 0.7 else "third_party_relevant"
    elif match_type == "domain_keyword":
        target_match = "third_party_relevant"
    elif match_type == "title_keyword" and official:
        target_match = "likely_target"
    elif match_type == "title_keyword":
        target_match = "third_party_relevant"
    elif authority == "low_value_aggregator":
        target_match = "unrelated"
    else:
        target_match = "weak_match"

    # relevance_score 0~1
    base_score = _TARGET_MATCH_WEIGHTS.get(match_type, 0.0) * match_score if match_score else 0.0
    authority_bonus = {"official": 0.2, "first_party_ecosystem": 0.1,
                       "reputable_third_party": 0.05, "unknown": 0, "low_value_aggregator": -0.2}
    relevance_score = round(min(1.0, max(0.0, base_score + authority_bonus.get(authority, 0))), 2)

    # default_selected：官方 + 高相关才默认勾选
    default_selected = (
        official and
        target_match in ("exact_target", "likely_target") and
        relevance_score >= 0.6
    )

    # relevance_reason
    reasons = []
    if official:
        reasons.append(f"官方来源 ({authority})")
    else:
        reasons.append(f"非官方 ({authority})")
    if target_match == "exact_target":
        reasons.append("精确URL匹配")
    elif target_match == "likely_target":
        reasons.append(f"高置信度匹配 (score={match_score:.2f})")
    elif target_match in ("third_party_relevant", "weak_match"):
        reasons.append("弱匹配或第三方报道")
    else:
        reasons.append("无目标匹配")

    return {
        "target_match_status": target_match,
        "relevance_score": relevance_score,
        "relevance_reason": "；".join(reasons),
        "source_authority": authority,
        "official_source": official,
        "default_selected": default_selected,
    }
