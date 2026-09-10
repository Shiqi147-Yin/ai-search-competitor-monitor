"""数据库 Migration 脚本
用法：
  python scripts/migrate_database.py --dry-run
  python scripts/migrate_database.py --apply
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


def main():
    parser = argparse.ArgumentParser(description="数据库 Migration 工具")
    parser.add_argument("--dry-run", action="store_true", help="预览缺失字段，不写数据库")
    parser.add_argument("--apply", action="store_true", help="执行增量 migration")
    args = parser.parse_args()

    if not args.dry_run and not args.apply:
        print("请指定 --dry-run 或 --apply")
        sys.exit(1)

    from config import DB_PATH
    print(f"\n数据库路径: {DB_PATH}")
    print(f"数据库存在: {Path(str(DB_PATH)).exists()}")
    print()

    database.init_db()

    # 定义需要检查的字段
    checks = {
        "querit_search_runs": [
            ("window_start", "TEXT"),
            ("window_end", "TEXT"),
            ("within_window_count", "INTEGER DEFAULT 0"),
            ("outside_window_count", "INTEGER DEFAULT 0"),
            ("missing_date_count", "INTEGER DEFAULT 0"),
            ("invalid_date_count", "INTEGER DEFAULT 0"),
            ("future_date_count", "INTEGER DEFAULT 0"),
        ],
        "querit_search_results": [
            ("normalized_published_at", "TEXT"),
            ("raw_published_date", "TEXT"),
            ("date_status", "TEXT DEFAULT 'missing'"),
            ("date_source", "TEXT"),
            ("date_confidence", "REAL DEFAULT 0.0"),
            ("freshness_status", "TEXT DEFAULT 'date_missing'"),
            ("days_from_search", "INTEGER"),
            ("date_conflict", "INTEGER DEFAULT 0"),
            ("freshness_reason", "TEXT"),
            ("window_start", "TEXT"),
            ("window_end", "TEXT"),
        ],
        "competitor_updates": [
            ("date_status", "TEXT"),
            ("date_source", "TEXT"),
            ("date_confidence", "REAL"),
        ],
    }

    any_missing = False
    for table, columns in checks.items():
        existing = database.get_table_columns(table)
        missing = [(c, s) for c, s in columns if c not in existing]
        present = [c for c, _ in columns if c in existing]

        print(f"表: {table}")
        print(f"  已有: {present}")
        if missing:
            any_missing = True
            print(f"  缺失: {[c for c,_ in missing]}")
            if args.apply:
                for col, sql in missing:
                    added = database.add_column_if_missing(table, col, sql)
                    status = "已添加" if added else "跳过（已存在）"
                    print(f"    + {col} {sql}  [{status}]")
        else:
            print(f"  全部字段已存在")
        print()

    if args.dry_run:
        if any_missing:
            print("存在缺失字段，请运行 --apply 补齐。")
        else:
            print("所有字段均已存在，无需 migration。")
    else:
        if any_missing:
            print("Migration 完成，所有缺失字段已补齐。")
        else:
            print("Migration 完成（无变更）。")
    print()
    print("重启 Streamlit？", "是（字段有变更）" if (any_missing and args.apply) else "否")


if __name__ == "__main__":
    main()
