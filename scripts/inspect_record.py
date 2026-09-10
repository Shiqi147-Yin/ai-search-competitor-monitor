"""inspect_record.py — 查询数据库记录并可选重新抓取

用法：
  python scripts/inspect_record.py --url "<URL>"
  python scripts/inspect_record.py --url "<URL>" --refetch
  python scripts/inspect_record.py --url "<URL>" --refetch --apply
"""
import sys
import io
import argparse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")


def main():
    parser = argparse.ArgumentParser(description="查询或重新抓取数据库中的记录")
    parser.add_argument("--url", required=True, help="要查询的 URL")
    parser.add_argument("--refetch", action="store_true", help="执行重新抓取（默认不更新数据库）")
    parser.add_argument("--apply", action="store_true", help="将重新抓取结果写入数据库（需同时传 --refetch）")
    args = parser.parse_args()

    import database
    database.init_db()
    database.migrate_db()

    from services.url_normalizer import normalize_url
    url = args.url.strip()
    norm = normalize_url(url)

    print(f"\n{'='*60}")
    print(f"URL: {url}")
    print(f"normalized: {norm}")

    # 查询已有记录
    existing = database.get_record_by_url(norm)
    if not existing:
        print("\n[数据库] 该 URL 不在数据库中。")
        if not args.refetch:
            return
    else:
        print("\n[数据库已有记录]")
        print(f"  id:             {existing['id']}")
        print(f"  competitor:     {existing.get('competitor') or '—'}")
        print(f"  source_platform:{existing.get('source_platform') or '—'}")
        print(f"  fetch_status:   {existing.get('fetch_status') or '—'}")
        print(f"  fetch_error:    {existing.get('fetch_error') or '—'}")
        print(f"  review_status:  {existing.get('review_status') or '—'}")
        print(f"  updated_at:     {(existing.get('updated_at') or '')[:19]}")

    if not args.refetch:
        return

    # 重新抓取
    from services.refetch_comparator import fetch_and_compare, apply_refetch_result
    print("\n[本次抓取]")
    comp = fetch_and_compare(url)

    if not comp:
        # URL 不在 DB，只做一次抓取显示
        from services.url_fetcher import fetch_url
        from services.source_detector import detect_both
        detected = detect_both(url)
        fr = fetch_url(url)
        print(f"  competitor:      {detected['competitor']}")
        print(f"  source_platform: {detected['source_platform']}")
        print(f"  fetch_status:    {fr.status}")
        print(f"  fetch_error:     {fr.error or '—'}")
        print(f"  title:           {(fr.title or '')[:80]}")
        print(f"\n（记录不存在于数据库，使用 scripts/debug_url_fetch.py 进行完整诊断）")
        return

    print(f"  competitor:      {comp.new_competitor}")
    print(f"  source_platform: {comp.new_platform}")
    print(f"  fetch_status:    {comp.new_fetch_status}")
    print(f"  fetch_error:     {comp.new_fetch_error or '—'}")
    print(f"  title:           {(comp.new_title or '')[:80]}")
    print(f"  needs_manual:    {comp.new_needs_manual}")
    print(f"  fetched_at:      {comp.fetched_at}")
    print(f"\n[状态变化] {comp.status_transition_msg}")

    if args.apply:
        print("\n[更新数据库]")
        result = apply_refetch_result(comp)
        if result["ok"]:
            print(f"  已更新 ID={result['record_id']}")
            print(f"  更新前：{result['old_status']}")
            print(f"  更新后：{result['new_status']}")
            print(f"  更新时间：{result['updated_at']}")
        else:
            print(f"  更新失败：{result['message']}")
    else:
        print("\n（默认不更新数据库，加 --apply 参数才写入）")


if __name__ == "__main__":
    main()
