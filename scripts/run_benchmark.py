"""真实 Benchmark 验证脚本"""
import sys, io
sys.path.insert(0, ".")
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
from env_loader import load_env; load_env()

from datetime import datetime, timezone, timedelta
from services.querit_client import search
from services.querit_query_builder import generate_queries
from services.querit_result_adapter import adapt_result
from services.freshness_filter import check_freshness
from services.benchmark_matcher import evaluate_recall, load_benchmark
from services.competitor_relevance_filter import classify_relevance, classify_source_authority

ref_time = datetime(2026, 7, 17, 12, 0, 0, tzinfo=timezone.utc)
time_window = 9  # July 8 - July 17

queries = generate_queries(["Tavily"], time_window, ["All"], ref_time)
print(f"生成 Query 数: {len(queries)}")
print()

all_results = []
for q in queries:
    q_text = q["generated_query"]
    qt = q["query_type"]
    run_res = search(q_text, 10)
    if run_res.success:
        for r in run_res.results:
            rec = adapt_result(r, "bench_diag", 1, "Tavily")
            if rec and not rec.get("_is_duplicate"):
                rec["_freshness"] = check_freshness(rec, time_window, ref_time)
                auth, official = classify_source_authority(rec["source_url"], "Tavily")
                rec["source_authority"] = auth
                rec["official_source"] = official
                all_results.append(rec)
    else:
        print(f"  FAIL [{qt}]: {run_res.error}")

print(f"总结果: {len(all_results)}")
events = load_benchmark("Tavily")
recall = evaluate_recall(all_results, "Tavily")
print(f"基准事件: {recall['expected_count']}")
print(f"已召回:   {recall['recalled_count']}")
print(f"未召回:   {recall['missed_count']}")
print(f"召回率:   {recall['recall_rate']:.0%}")
print()
print("各来源分布:")
from collections import Counter
auth_counts = Counter(r.get("source_authority","?") for r in all_results)
for k, v in auth_counts.most_common():
    print(f"  {k}: {v}")
print()
if recall["missed_events"]:
    print("未召回事件:")
    for ev in recall["missed_events"]:
        print(f"  - {ev['title']}")
        print(f"    {ev['url']}")
