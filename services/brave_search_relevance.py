"""Brave Search relevance filter
判断 Blog 文章/Docs 页面/GitHub commit 是否与 Brave Search API 相关。
不依赖于 Brave Browser / Wallet / Rewards / VPN。
"""
import re
from dataclasses import dataclass

# ── 关键词分组 ─────────────────────────────────────────────────

# 明确属于 Search API / Search product 的关键词
_SEARCH_API_KEYWORDS = [
    "search api", "brave search", "web search", "news search",
    "image search", "video search", "local search", "place search",
    "llm context", "search endpoint", "search sdk", "search skill",
    "search result", "search index", "search ranking", "search query",
    "search integration", "search for ai", "search for agent",
    "rag", "grounding", "independent search", "goggles",
    "search infrastructure", "brave api", "search-api",
    "search api pricing", "search subscription", "api key",
    "spellcheck api", "suggest api", "summarizer api",
    "search mcp", "search for rag", "search for llm",
]

# 明确属于非 Search 产品的关键词（优先排除）
_NON_SEARCH_KEYWORDS = [
    "brave browser", "brave desktop", "brave android", "brave ios",
    "brave mobile", "brave wallet", "brave rewards", "brave vpn",
    "brave shields", "brave ads", "brave sync", "brave leo",
    "brave talk", "brave games", "bat token", "bat roadmap",
    "basic attention token", "containers feature", "tab feature",
    "browser release", "browser update", "browser v1.", "browser version",
    "de-amp", "web discovery", "brave news feed",
]

# URL 路径中明确属于 Search 的模式
_SEARCH_URL_PATTERNS = re.compile(
    r"(/search/|/search-api|brave-search|search-news|"
    r"llm-context|search-sdk|search-mcp|search-skill)",
    re.IGNORECASE,
)

# URL 路径中明确属于非 Search 的模式
_NON_SEARCH_URL_PATTERNS = re.compile(
    r"(/wallet|/rewards|/vpn|/shields|/leo|/ads/|"
    r"/bat-|/browser-|/containers|/android|/ios|/mobile|"
    r"brave-talk|brave-games|/nft|/crypto|/sync)",
    re.IGNORECASE,
)


@dataclass
class SearchRelevanceResult:
    is_search_related: bool = False
    search_relevance_score: float = 0.0
    search_relevance_reason: str = ""
    brave_product_area: str = "other"  # search_api / search_product / search_integration / browser / wallet / other


def classify_brave_search_relevance(
    title: str,
    url: str,
    summary: str = "",
) -> SearchRelevanceResult:
    """判断 Brave 内容是否与 Search API 相关。

    返回 is_search_related=True 的内容进入主结果。
    is_search_related=False 的内容进入诊断区。
    """
    result = SearchRelevanceResult()
    combined = f"{title} {url} {summary}".lower()
    url_lower = url.lower()

    # ── 1. URL 路径明确属于非 Search → 直接排除 ─────────────────
    if _NON_SEARCH_URL_PATTERNS.search(url_lower):
        result.is_search_related = False
        result.search_relevance_score = 0.0
        result.brave_product_area = _classify_product_area(url_lower, combined)
        result.search_relevance_reason = f"Non-search URL pattern: {url_lower[:60]}"
        return result

    # ── 2. 标题/摘要含非 Search 产品词 → 排除（除非同时有 search 关键词）─
    non_search_hits = [kw for kw in _NON_SEARCH_KEYWORDS if kw in combined]
    search_hits = [kw for kw in _SEARCH_API_KEYWORDS if kw in combined]

    if non_search_hits and not search_hits:
        result.is_search_related = False
        result.search_relevance_score = 0.1
        result.brave_product_area = _classify_product_area(url_lower, combined)
        result.search_relevance_reason = f"Non-search keywords: {non_search_hits[:2]}"
        return result

    # ── 3. URL 路径明确属于 Search ────────────────────────────────
    if _SEARCH_URL_PATTERNS.search(url_lower):
        result.is_search_related = True
        result.search_relevance_score = 0.9
        result.brave_product_area = "search_api"
        result.search_relevance_reason = f"Search URL pattern: {url_lower[:60]}"
        return result

    # ── 4. 标题/摘要含 Search 关键词 ─────────────────────────────
    if search_hits:
        score = min(0.5 + len(search_hits) * 0.1, 1.0)
        result.is_search_related = True
        result.search_relevance_score = score
        result.brave_product_area = "search_product" if "search api" in combined else "search_product"
        result.search_relevance_reason = f"Search keywords: {search_hits[:3]}"
        return result

    # ── 5. 默认：无法确认 → 低分，非主结果 ───────────────────────
    result.is_search_related = False
    result.search_relevance_score = 0.15
    result.brave_product_area = "other"
    result.search_relevance_reason = "No search-related keywords found"
    return result


def _classify_product_area(url_lower: str, combined: str) -> str:
    """细分 brave_product_area。"""
    if any(w in combined for w in ("wallet", "bat ", "token")):
        return "wallet"
    if any(w in combined for w in ("rewards", "creator")):
        return "rewards"
    if "vpn" in combined:
        return "vpn"
    if any(w in combined for w in ("browser", "shields", "leo", "sync", "container")):
        return "browser"
    return "other"


def filter_brave_items_by_search_relevance(items: list) -> tuple[list, list, dict]:
    """过滤 Blog/Docs items，只保留 Search-related 内容。

    Returns:
        (search_related, filtered_out, stats)
    """
    search_related = []
    filtered_out = []

    for item in items:
        url = getattr(item, "source_url", "") or ""
        title = getattr(item, "update_title", "") or getattr(item, "title", "") or ""
        summary = getattr(item, "summary", "") or ""

        rel = classify_brave_search_relevance(title, url, summary)
        # 附加相关性字段
        item.brave_search_relevance = rel.is_search_related
        item.brave_search_score = rel.search_relevance_score
        item.brave_search_reason = rel.search_relevance_reason
        item.brave_product_area = rel.brave_product_area

        if rel.is_search_related:
            search_related.append(item)
        else:
            filtered_out.append(item)

    stats = {
        "scanned": len(items),
        "search_related": len(search_related),
        "filtered_non_search": len(filtered_out),
    }
    return search_related, filtered_out, stats
