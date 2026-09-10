"""漏召回事件诊断服务
对每条未召回基准事件执行三种精确 Query，判断问题来源。
不写正式数据库。
"""
from dataclasses import dataclass, field
from typing import Optional
from urllib.parse import urlparse

from services.querit_client import search, SearchRunResult
from services.benchmark_matcher import load_benchmark


@dataclass
class QueryVariantResult:
    variant_name: str = ""         # title_exact / domain_targeted / url_slug
    executed_query: str = ""
    result_count: int = 0
    target_url_found: bool = False
    target_title_found: bool = False
    closest_result_title: str = ""
    closest_result_url: str = ""
    closest_similarity: float = 0.0
    api_status: str = ""
    parse_invalid_count: int = 0


@dataclass
class EventDiagnosticResult:
    event_id: str = ""
    event_title: str = ""
    event_url: str = ""
    variants: list = field(default_factory=list)   # list[QueryVariantResult]
    final_diagnosis: str = "unknown"
    diagnosis_reason: str = ""


def _build_diagnostic_queries(event: dict) -> list[tuple[str, str]]:
    """生成三种诊断 Query：精确标题 / 域名定向 / URL slug。"""
    title = event.get("title", "")
    url = event.get("primary_url", "")
    keywords = event.get("keywords", [])
    domains = event.get("expected_domains", [])
    kw_str = " ".join(keywords[:4]) if keywords else title

    # A. 精确标题
    q_title = f'Find the official Tavily page titled "{title}".'
    if keywords:
        q_title += f" Keywords: {kw_str}."

    # B. 域名定向
    domain = domains[0] if domains else "tavily.com"
    q_domain = (
        f"Search {domain} for Tavily {kw_str}. "
        f"Return only pages from {domain}."
    )

    # C. URL slug
    slug = ""
    if url:
        path = urlparse(url).path.strip("/")
        slug = path.split("/")[-1] if "/" in path else path
    if slug:
        q_slug = f'Find a Tavily page whose URL contains "{slug}". Topic: {kw_str}.'
    else:
        q_slug = f"Find Tavily {kw_str} official page."

    return [
        ("title_exact", q_title),
        ("domain_targeted", q_domain),
        ("url_slug", q_slug),
    ]


def _url_match_diag(result_url: str, expected_url: str) -> bool:
    def _norm(u: str) -> str:
        return u.strip().rstrip("/").lower().replace("http://", "https://")
    na = _norm(result_url)
    nb = _norm(expected_url)
    if na == nb:
        return True
    # Path 包含匹配
    try:
        pa = urlparse(result_url).path.rstrip("/").lower()
        pb = urlparse(expected_url).path.rstrip("/").lower()
        if pa and pb and len(pa) > 5 and (pa in pb or pb in pa):
            da = urlparse(result_url).netloc.lower().lstrip("www.")
            db = urlparse(expected_url).netloc.lower().lstrip("www.")
            if da == db or da in db or db in da:
                return True
    except Exception:
        pass
    return False


def _title_match_diag(result_title: str, event_title: str) -> bool:
    r = result_title.lower()
    e = event_title.lower()
    return e[:30] in r or r[:30] in e


def _closest_result(results, target_url: str, target_title: str) -> tuple[str, str, float]:
    best_score = 0.0
    best_title = ""
    best_url = ""
    for r in results:
        url = r.url or ""
        title = r.title or ""
        score = 0.0
        if _url_match_diag(url, target_url):
            score = 1.0
        elif _title_match_diag(title, target_title):
            score = 0.7
        elif any(kw in url.lower() or kw in title.lower()
                 for kw in target_title.lower().split()[:3]):
            score = 0.3
        if score > best_score:
            best_score = score
            best_title = title
            best_url = url
    return best_title, best_url, best_score


def diagnose_missed_event(event: dict, num_results: int = 5) -> EventDiagnosticResult:
    """对单条漏召回事件执行三种 Query 诊断。不写数据库。"""
    diag = EventDiagnosticResult(
        event_id=event.get("id", ""),
        event_title=event.get("title", ""),
        event_url=event.get("primary_url", ""),
    )

    variants = _build_diagnostic_queries(event)

    for variant_name, query in variants:
        vr = QueryVariantResult(variant_name=variant_name, executed_query=query)

        run_res: SearchRunResult = search(query, num_results)
        vr.api_status = "success" if run_res.success else f"failed:{run_res.error}"
        vr.parse_invalid_count = run_res.invalid_result_count

        if run_res.success:
            vr.result_count = len(run_res.results)
            for r in run_res.results:
                if _url_match_diag(r.url or "", diag.event_url):
                    vr.target_url_found = True
                if _title_match_diag(r.title or "", diag.event_title):
                    vr.target_title_found = True

            ct, cu, cs = _closest_result(run_res.results, diag.event_url, diag.event_title)
            vr.closest_result_title = ct
            vr.closest_result_url = cu
            vr.closest_similarity = cs

        diag.variants.append(vr)

    # ── 诊断逻辑 ────────────────────────────────────────────
    all_success = all(v.api_status == "success" for v in diag.variants)
    title_found_by_any = any(v.target_url_found or v.target_title_found for v in diag.variants)
    title_found_by_exact = any(
        v.target_url_found or v.target_title_found
        for v in diag.variants if v.variant_name == "title_exact"
    )
    title_found_by_broad = any(
        v.target_url_found or v.target_title_found
        for v in diag.variants if v.variant_name in ("domain_targeted", "url_slug")
    )

    if not all_success:
        diag.final_diagnosis = "unknown"
        diag.diagnosis_reason = "部分 API 请求失败，无法完成完整诊断"
    elif title_found_by_any:
        if title_found_by_exact and not title_found_by_broad:
            diag.final_diagnosis = "query_strategy_issue"
            diag.diagnosis_reason = "精确标题 Query 能找到目标，但宽泛 Query 未返回；建议优化常规检索策略"
        else:
            diag.final_diagnosis = "benchmark_matching_issue"
            diag.diagnosis_reason = (
                "API 已返回目标 URL/标题，但之前的 Benchmark 匹配器未识别；"
                "匹配规则已修复，下次检索应能正常召回"
            )
    else:
        all_zero = all(v.result_count == 0 for v in diag.variants if v.api_status == "success")
        if all_zero:
            diag.final_diagnosis = "probable_index_coverage_gap"
            diag.diagnosis_reason = "三种 Query 均返回 0 结果；API 可能未索引目标页面"
        else:
            diag.final_diagnosis = "probable_index_coverage_gap"
            diag.diagnosis_reason = "三种精确 Query 均未找到目标 URL 或标题；API 索引覆盖不足"

    return diag


def diagnose_all_missed(
    competitor: str = "Tavily",
    missed_ids: Optional[list] = None,
    num_results: int = 5,
) -> list[EventDiagnosticResult]:
    """诊断全部（或指定）漏召回事件。单个失败不影响其他。"""
    events = load_benchmark(competitor)
    if missed_ids:
        events = [e for e in events if e.get("id") in missed_ids]

    results = []
    for event in events:
        try:
            diag = diagnose_missed_event(event, num_results)
            results.append(diag)
        except Exception as e:
            results.append(EventDiagnosticResult(
                event_id=event.get("id", ""),
                event_title=event.get("title", ""),
                event_url=event.get("primary_url", ""),
                final_diagnosis="unknown",
                diagnosis_reason=f"诊断异常: {type(e).__name__}: {str(e)[:80]}",
            ))
    return results
