"""多来源检索编排服务
支持按来源拆分 Query、两轮检索、结果合并去重、Benchmark 模式。
"""
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional
import uuid

from services.querit_query_builder import generate_queries
from services.querit_client import search, SearchRunResult
from services.querit_result_adapter import adapt_results
from services.freshness_filter import check_freshness, FreshnessResult
from services.benchmark_matcher import match_result_to_events, load_benchmark
from services.competitor_relevance_filter import classify_relevance
from services.url_normalizer import normalize_url


@dataclass
class SourceQueryStats:
    query_type: str = ""
    source_target: str = ""
    competitor: str = ""
    result_count: int = 0
    official_result_count: int = 0
    within_window_count: int = 0
    matched_benchmark_event_count: int = 0
    low_value_result_count: int = 0
    error: str = ""


@dataclass
class OrchestrationResult:
    run_id: str = ""
    all_results: list = field(default_factory=list)        # list[dict] enriched records
    query_stats: list = field(default_factory=list)        # list[SourceQueryStats]
    total_raw: int = 0
    unique_count: int = 0
    within_window_count: int = 0
    outside_window_count: int = 0
    missing_date_count: int = 0
    benchmark_recall: Optional[dict] = None               # from evaluate_recall()
    errors: list = field(default_factory=list)


def run_targeted_search(
    competitors: list[str],
    time_window_days: int,
    source_scope: Optional[list[str]] = None,
    result_per_query: int = 10,
    reference_time: Optional[datetime] = None,
    benchmark_mode: bool = False,
    progress_callback=None,
) -> OrchestrationResult:
    """
    执行分来源定向检索，返回 OrchestrationResult。
    - 每种来源独立执行 Query
    - 自动去重（normalized_url）
    - 计算新鲜度和相关性
    - 可选 benchmark 召回评估
    单条 Query 失败不中断其他 Query。
    """
    ref_time = reference_time or datetime.now(timezone.utc)
    run_id = str(uuid.uuid4())[:8]
    orch = OrchestrationResult(run_id=run_id)

    queries = generate_queries(competitors, time_window_days, source_scope, ref_time)
    total_queries = len(queries)
    seen_normalized: set[str] = set()

    for idx, qinfo in enumerate(queries):
        if progress_callback:
            progress_callback(idx, total_queries, qinfo.get("query_type", ""))

        q_text = qinfo["generated_query"]
        q_comp = qinfo.get("competitor", "Other")
        qt = qinfo.get("query_type", "")
        source_target = qinfo.get("source_target", "")

        stats = SourceQueryStats(
            query_type=qt, source_target=source_target, competitor=q_comp,
        )

        run_res: SearchRunResult = search(q_text, result_per_query)

        if not run_res.success:
            stats.error = run_res.error
            orch.errors.append(f"[{qt}] {run_res.error}")
            orch.query_stats.append(stats)
            continue

        adapted = adapt_results(run_res.results, run_id, idx, q_comp)
        stats.result_count = len(adapted)

        # 加载基准事件（benchmark 模式下使用）
        benchmark_events = load_benchmark(q_comp) if benchmark_mode else []

        for rec in adapted:
            norm = rec.get("normalized_url") or normalize_url(rec.get("source_url", ""))
            if norm in seen_normalized:
                rec["_is_dedup_run"] = True
            else:
                seen_normalized.add(norm)

            # 新鲜度
            fr: FreshnessResult = check_freshness(rec, time_window_days, ref_time)
            rec["_freshness"] = fr
            if fr.freshness_status == "within_window":
                orch.within_window_count += 1
                stats.within_window_count += 1
            elif fr.freshness_status == "outside_window":
                orch.outside_window_count += 1
            else:
                orch.missing_date_count += 1

            # 相关性评分
            match_event_id, match_type, match_score = (
                match_result_to_events(rec, benchmark_events)
                if benchmark_mode else (None, "no_match", 0.0)
            )
            relevance = classify_relevance(rec, q_comp, match_type, match_score)
            rec.update(relevance)

            if relevance["source_authority"] == "low_value_aggregator":
                stats.low_value_result_count += 1
            if relevance["official_source"]:
                stats.official_result_count += 1
            if match_event_id:
                stats.matched_benchmark_event_count += 1

            # 最终默认选择：必须是官方+窗口内+高相关+非重复
            rec["_should_select"] = (
                relevance["official_source"] and
                fr.freshness_status == "within_window" and
                relevance["target_match_status"] in ("exact_target", "likely_target") and
                not rec.get("_is_duplicate") and
                not rec.get("_is_dedup_run")
            )

            orch.all_results.append(rec)

        orch.query_stats.append(stats)

    orch.total_raw = len(orch.all_results)
    orch.unique_count = len(seen_normalized)

    # Benchmark 召回评估
    if benchmark_mode and competitors:
        from services.benchmark_matcher import evaluate_recall
        # 只用非重复结果
        unique_results = [r for r in orch.all_results if not r.get("_is_dedup_run")]
        orch.benchmark_recall = evaluate_recall(unique_results, competitors[0])

    if progress_callback:
        progress_callback(total_queries, total_queries, "完成")

    return orch
