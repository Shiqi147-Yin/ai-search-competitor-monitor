"""诊断漏召回事件脚本
用法：
  python scripts/diagnose_benchmark_misses.py --competitor Tavily
  python scripts/diagnose_benchmark_misses.py --competitor Tavily --event-ids id1,id2
"""
import sys
import io
import argparse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

from env_loader import load_env
load_env()

from services.benchmark_diagnostics import diagnose_all_missed


def main():
    parser = argparse.ArgumentParser(description="Benchmark 漏召回事件诊断")
    parser.add_argument("--competitor", default="Tavily")
    parser.add_argument("--event-ids", default="",
                        help="逗号分隔的事件 ID，不传则诊断全部")
    parser.add_argument("--num-results", type=int, default=5)
    args = parser.parse_args()

    missed_ids = [i.strip() for i in args.event_ids.split(",") if i.strip()] or None
    print(f"\n=== {args.competitor} 漏召回事件诊断 ===\n")

    results = diagnose_all_missed(args.competitor, missed_ids, args.num_results)
    summary: dict[str, int] = {}

    for diag in results:
        print(f"{'='*55}")
        print(f"事件: {diag.event_title}")
        print(f"URL:  {diag.event_url}")
        print()
        for vr in diag.variants:
            found_flag = "✅" if (vr.target_url_found or vr.target_title_found) else "❌"
            print(f"  [{vr.variant_name}] {found_flag}  结果数: {vr.result_count}  API: {vr.api_status}")
            print(f"    Query: {vr.executed_query[:90]}")
            if vr.target_url_found:
                print(f"    ✅ 找到目标 URL")
            if vr.target_title_found:
                print(f"    ✅ 找到目标标题")
            if vr.closest_result_title and not (vr.target_url_found or vr.target_title_found):
                print(f"    最接近: {vr.closest_result_title[:65]}")
                print(f"             {vr.closest_result_url[:65]}")
            print()

        diag_type = diag.final_diagnosis
        summary[diag_type] = summary.get(diag_type, 0) + 1
        print(f"  最终诊断: [{diag_type}]")
        print(f"  原因:     {diag.diagnosis_reason}")
        print()

    print(f"\n=== 汇总 ===")
    for k, v in summary.items():
        if v:
            print(f"  {k}: {v} 条")


if __name__ == "__main__":
    main()
