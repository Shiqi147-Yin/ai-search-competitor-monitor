"""批量分析历史待审核记录

用法：
  python scripts/analyze_pending_records.py --dry-run
  python scripts/analyze_pending_records.py --apply
  python scripts/analyze_pending_records.py --apply --limit 20
  python scripts/analyze_pending_records.py --recompute --dry-run
  python scripts/analyze_pending_records.py --recompute --apply
"""
import sys
import io
import argparse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")


def main():
    parser = argparse.ArgumentParser(description="批量分析待审核记录")
    parser.add_argument("--dry-run", action="store_true", help="预览模式，不写入数据库")
    parser.add_argument("--apply", action="store_true", help="正式执行分析并写入 auto_* 字段")
    parser.add_argument("--recompute", action="store_true",
                        help="重新计算已有 analyzed/partial 记录的分析结果（不覆盖人工字段）")
    parser.add_argument("--limit", type=int, default=0, help="最多处理 N 条（0=不限制）")
    args = parser.parse_args()

    if not args.dry_run and not args.apply:
        print("请指定 --dry-run 或 --apply")
        sys.exit(1)

    import database
    database.init_db()
    database.migrate_db()

    from services.content_analyzer import analyze_record

    # 查询条件
    if args.recompute:
        # 重新计算：包含已有 analyzed / partial / pending 的待审核记录
        query = """SELECT * FROM competitor_updates
                   WHERE review_status = '待审核'
                   ORDER BY collected_at DESC"""
    else:
        # 首次分析：只处理 analysis_status 为空/failed/partial/pending 的记录
        query = """SELECT * FROM competitor_updates
                   WHERE review_status = '待审核'
                   AND (analysis_status IS NULL OR analysis_status = '' OR
                        analysis_status = 'failed' OR analysis_status = 'partial' OR
                        analysis_status = 'pending')
                   ORDER BY collected_at DESC"""

    with database._get_conn() as conn:
        rows = conn.execute(query).fetchall()

    records = [dict(r) for r in rows]
    total = len(records)

    if args.limit and args.limit > 0:
        records = records[:args.limit]

    print(f"\n{'='*60}")
    mode = "重新计算" if args.recompute else "首次分析"
    print(f"待{mode}记录：{total} 条"
          + (f"（本次处理 {args.limit} 条）" if args.limit else ""))
    print(f"模式：{'预览（不写入）' if args.dry_run else f'正式{mode}（写入 auto_* 字段）'}")
    print(f"{'='*60}\n")

    stats = {"analyzed": 0, "partial": 0, "pending": 0, "failed": 0}

    for rec in records:
        rec_id = rec["id"]
        url = rec.get("source_url") or ""
        title = rec.get("title") or ""
        old_conf = rec.get("analysis_confidence") or 0.0

        try:
            result = analyze_record(rec)
            status = result.analysis_status if result.analysis_status in stats else "analyzed"
            stats[status] += 1

            conf_change = ""
            if args.recompute and old_conf:
                diff = result.analysis_confidence - old_conf
                sign = "+" if diff >= 0 else ""
                conf_change = f"  [置信度变化: {old_conf:.0%} → {result.analysis_confidence:.0%} ({sign}{diff:.0%})]"

            print(f"  [{status.upper()}] ID={rec_id}  {title[:45] or url[:45]}")
            print(f"          → 分类: {result.auto_category}  "
                  f"优先级: {result.auto_priority}  "
                  f"置信度: {result.analysis_confidence:.0%}  "
                  f"依据: {result.evidence_source}{conf_change}")

            if args.apply:
                db_fields = result.to_db_fields()
                database.update_record(rec_id, db_fields)

        except Exception as e:
            stats["failed"] += 1
            print(f"  [FAILED] ID={rec_id}  {str(e)[:60]}")

    print(f"\n{'='*60}")
    print(f"处理完成：共 {len(records)} 条")
    print(f"  已分析   : {stats.get('analyzed', 0)}")
    print(f"  部分分析 : {stats.get('partial', 0)}")
    print(f"  待评估   : {stats.get('pending', 0)}")
    print(f"  失败     : {stats.get('failed', 0)}")
    if args.dry_run:
        print("\n（预览模式，未写入数据库）")
    else:
        print("\n（已写入 auto_* 字段，人工字段未被修改）")


if __name__ == "__main__":
    main()
