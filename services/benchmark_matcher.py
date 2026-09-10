"""基准事件匹配服务
将检索结果与人工基准集对照，判断是否召回了预期事件。
不直接写正式竞品数据库。
"""
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse
import yaml


_BENCHMARK_PATH = Path(__file__).parent.parent / "config" / "competitor_benchmark.yaml"


def load_benchmark(competitor: str = "Tavily") -> list[dict]:
    """加载指定竞品的基准事件列表。"""
    try:
        with open(_BENCHMARK_PATH, encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
        return data.get(competitor, {}).get("expected_events", [])
    except Exception:
        return []


def _normalize_domain(url: str) -> str:
    try:
        netloc = urlparse(url).netloc.lower()
        return netloc.lstrip("www.")
    except Exception:
        return ""


def _url_match(result_url: str, expected_url: str) -> bool:
    """完整 URL 归一化后比较，支持 URL slug 子串匹配（处理带查询参数的 GitHub URL）。"""
    def _norm(u: str) -> str:
        u = u.strip().rstrip("/").lower()
        if u.startswith("http://"):
            u = "https://" + u[7:]
        # 去除追踪参数
        from urllib.parse import urlparse, urlunparse, parse_qs, urlencode
        try:
            p = urlparse(u)
            # 去除 since/until 等参数后比较
            qs = {k: v for k, v in parse_qs(p.query).items()
                  if k not in ("since", "until", "utm_source", "utm_medium", "ref")}
            cleaned = urlunparse((p.scheme, p.netloc, p.path, p.params, urlencode(qs, doseq=True), ""))
            return cleaned
        except Exception:
            return u

    na = _norm(result_url)
    nb = _norm(expected_url)

    if na == nb:
        return True

    # Path 包含匹配（处理路径不完全相同但指向同一页面）
    try:
        from urllib.parse import urlparse
        pa = urlparse(result_url).path.rstrip("/").lower()
        pb = urlparse(expected_url).path.rstrip("/").lower()
        if pa and pb and (pa in pb or pb in pa):
            # 同一域名下的路径匹配
            da = _normalize_domain(result_url)
            db = _normalize_domain(expected_url)
            if da == db or da in db or db in da:
                return True
    except Exception:
        pass

    return False


def _domain_match(result_url: str, expected_domains: list[str]) -> bool:
    netloc = _normalize_domain(result_url)
    return any(d in netloc for d in expected_domains)


def _keyword_score(text: str, keywords: list[str]) -> float:
    """返回关键词命中比例 0.0~1.0。"""
    if not keywords:
        return 0.0
    text_lower = text.lower()
    hits = sum(1 for kw in keywords if kw.lower() in text_lower)
    return hits / len(keywords)


def match_result_to_events(
    result: dict,
    events: list[dict],
    title_threshold: float = 0.5,
    keyword_threshold: float = 0.3,
) -> tuple[Optional[str], str, float]:
    """
    将单条结果与基准事件列表对比（宽松版）。
    Returns (matched_event_id | None, match_type, match_score)
    """
    url = result.get("source_url") or result.get("url") or ""
    title = result.get("title") or ""
    summary = result.get("summary") or result.get("querit_raw_summary") or ""
    raw_content = result.get("raw_content") or ""
    combined_text = f"{title} {summary} {raw_content}".lower()

    for event in events:
        event_id = event.get("id", "")
        primary_url = event.get("primary_url", "")
        expected_domains = event.get("expected_domains", [])
        keywords = event.get("keywords", [])
        event_title = event.get("title", "")

        # 1. 精确 URL 匹配（含路径子串）
        if primary_url and _url_match(url, primary_url):
            return event_id, "exact_url", 1.0

        # 2. 标题高度相似（支持事件标题关键词在结果标题中出现）
        event_title_lower = event_title.lower()
        title_lower = title.lower()
        # 取事件标题的前几个词检查
        event_title_words = [w for w in event_title_lower.split() if len(w) > 3]
        if event_title_words:
            match_word_count = sum(1 for w in event_title_words if w in title_lower)
            title_sim = match_word_count / len(event_title_words)
            if title_sim >= 0.5:
                return event_id, "title_match", round(title_sim, 2)

        # 3. 域名 + 关键词组合匹配
        kw_score = _keyword_score(combined_text, keywords)
        if _domain_match(url, expected_domains) and kw_score >= keyword_threshold:
            return event_id, "domain_keyword", kw_score

        # 4. 纯关键词匹配（不限域名，阈值更高）
        if kw_score >= title_threshold:
            return event_id, "title_keyword", kw_score

    return None, "no_match", 0.0


def evaluate_recall(
    results: list[dict],
    competitor: str = "Tavily",
) -> dict:
    """
    计算基准召回率。

    Returns dict with:
      expected_count, recalled_count, missed_count, recall_rate,
      recalled_events, missed_events, match_details
    """
    events = load_benchmark(competitor)
    if not events:
        return {
            "expected_count": 0, "recalled_count": 0, "missed_count": 0,
            "recall_rate": 0.0, "recalled_events": [], "missed_events": [],
            "match_details": [],
        }

    recalled_ids: set[str] = set()
    match_details = []

    for result in results:
        event_id, match_type, score = match_result_to_events(result, events)
        if event_id:
            recalled_ids.add(event_id)
            match_details.append({
                "result_url": result.get("source_url") or result.get("url") or "",
                "result_title": result.get("title") or "",
                "matched_event_id": event_id,
                "match_type": match_type,
                "score": round(score, 2),
            })

    all_ids = {e["id"] for e in events}
    missed_ids = all_ids - recalled_ids
    recall_rate = len(recalled_ids) / len(events) if events else 0.0

    return {
        "expected_count": len(events),
        "recalled_count": len(recalled_ids),
        "missed_count": len(missed_ids),
        "recall_rate": round(recall_rate, 3),
        "recalled_events": list(recalled_ids),
        "missed_events": [
            {"id": e["id"], "title": e["title"], "url": e.get("primary_url", "")}
            for e in events if e["id"] in missed_ids
        ],
        "match_details": match_details,
    }
