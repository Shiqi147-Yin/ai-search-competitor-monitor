"""重新计算历史检索结果的新鲜度状态
用法：
  python scripts/recompute_result_freshness.py --dry-run
  python scripts/recompute_result_freshness.py --run-id 4 --dry-run
  python scripts/recompute_result_freshness.py --run-id 4 --apply
"""
import sys
import io
import argparse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

from env_loader import load_env
load_env()

import database
from services.freshness_filter import check_freshness, freshness_summary
from datetime import datetime, timezone


def main():
    parser = argparse.ArgumentParser(description="重新计算历史检索结果新鲜度")
    parser.add_argument("--dry-run", action="store_true", help="预览模式，不写数据库")
    parser.add_argument("--apply", action="store_true", help="正式写入新鲜度字段")
    parser.add_argument("--run-id", type=int, default=0, help="指定 run_id（0=全部）")
    args = parser.parse_args()

    if not args.dry_run and not args.apply:
        print("请指定 --dry-run 或 --apply")
        sys.exit(1)

    database.init_db()
    database.migrate_db()

    # 查询目标批次
    if args.run_id:
        runs = [r for r in database.get_search_runs(limit=1000) if r["id"] == args.run_id]
        if not runs:
            print(f"未找到 run_id={args.run_id}")
            sys.exit(1)
    else:
        runs = database.get_search_runs(limit=1000)

    print(f"\n{'='*60}")
    print(f"目标批次: {len(runs)} 个  |  模式: {'预览' if args.dry_run else '正式写入'}")
    print(f"{'='*60}\n")

    total_updated = 0
    for run in runs:
        run_id = run["id"]
        time_window = run.get("time_window_days") or 7
        started_at = run.get("started_at") or run.get("created_at")
        try:
            ref_time = datetime.fromisoformat(started_at.replace("Z", "+00:00"))
        except Exception:
            ref_time = datetime.now(timezone.utc)

        results = database.get_search_results(run_id)
        print(f"Run {run_id}（{started_at[:10] if started_at else '?'}，{time_window}天窗口）：{len(results)} 条结果")

        fr_before = {"within_window": 0, "outside_window": 0,
                     "date_missing": 0, "date_invalid": 0, "future_date": 0}
        fr_after = dict(fr_before)

        for res in results:
            old_status = res.get("freshness_status", "date_missing")
            key_old = old_status if old_status in fr_before else "date_missing"
            fr_before[key_old] += 1

            # 构建用于新鲜度检查的伪记录
            pseudo_rec = {
                "publish_date": res.get("published_date") or res.get("raw_published_date"),
                "published_date": res.get("published_date") or res.get("raw_published_date"),
                "page_age": res.get("normalized_published_at"),
                "source_url": res.get("source_url", ""),
                "title": res.get("title", ""),
            }
            fr = check_freshness(pseudo_rec, time_window, ref_time)
            key_new = fr.freshness_status if fr.freshness_status in fr_after else "date_missing"
            fr_after[key_new] += 1
            total_updated += 1

            if args.apply:
                # 只更新新鲜度相关字段，不改变原始日期
                with database._get_conn() as conn:
                    conn.execute(
                        """UPDATE querit_search_results SET
                           normalized_published_at=?, date_status=?, date_source=?,
                           date_confidence=?, freshness_status=?, days_from_search=?,
                           freshness_reason=?, window_start=?, window_end=?
                           WHERE id=?""",
                        (
                            fr.normalized_published_at,
                            fr.date_status,
                            fr.date_source,
                            fr.date_confidence,
                            fr.freshness_status,
                            fr.days_from_search,
                            fr.freshness_reason,
                            fr.window_start,
                            fr.window_end,
                            res["id"],
                        ),
                    )
                    conn.commit()

        print(f"  更新前: {fr_before}")
        print(f"  更新后: {fr_after}")

    print(f"\n{'='*60}")
    print(f"共处理 {total_updated} 条结果")
    print("（预览模式，未写入数据库）" if args.dry_run else "（已写入新鲜度字段）")


if __name__ == "__main__":
    main()
