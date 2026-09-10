"""诊断脚本：追踪 Brave Blog in-window 记录为何未进入最终候选
用法：
    python scripts/debug_brave_blog_candidates.py \
        --start-date 2026-07-01 \
        --end-date 2026-07-15
"""
import sys
import os
import io

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

# Windows UTF-8 输出
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

import argparse
from services.official_source_monitor import run_official_monitor
from services.official_monitor_importer import filter_valid_results


def main():
    parser = argparse.ArgumentParser(description="Brave Blog 候选诊断")
    parser.add_argument("--start-date", default="2026-07-01")
    parser.add_argument("--end-date", default="2026-07-15")
    args = parser.parse_args()

    print(f"\n>>> Brave Blog 候选链路诊断")
    print(f"    窗口: {args.start_date} ~ {args.end_date}")
    print()

    result = run_official_monitor(
        competitor="Brave",
        window_start=args.start_date,
        window_end=args.end_date,
        source_types=["all"],
        enable_querit_supplement=False,
    )

    # ── 统计字段打印 ───────────────────────────────────────────────
    blog_stat = result.source_stats.get("blog", {})
    funnel = result.source_stats.get("blog_funnel", {})
    brave_filter = result.source_stats.get("brave_search_filter", {})

    print("=" * 60)
    print("  来源统计")
    print("=" * 60)
    print(f"  blog (pre-filter) found     = {blog_stat.get('found', 0)}")
    print(f"  blog (pre-filter) in_window = {blog_stat.get('in_window', 0)}")
    print()
    print(f"  brave_search_filter:")
    print(f"    input   = {brave_filter.get('scanned', 0)}")
    print(f"    kept    = {brave_filter.get('search_related', 0)}")
    print(f"    filtered= {brave_filter.get('filtered_non_search', 0)}")
    print()
    print(f"  blog_funnel (post search-filter):")
    print(f"    discovered      = {funnel.get('blog_discovered', 0)}")
    print(f"    search_related  = {funnel.get('blog_search_related', 0)}")
    print(f"    non_search_filt = {funnel.get('blog_non_search_filtered', 0)}")
    print(f"    in_window       = {funnel.get('blog_in_window', 0)}")
    print(f"    outside_window  = {funnel.get('blog_outside_window', 0)}")
    print(f"    invalid_date    = {funnel.get('blog_invalid_date', 0)}")

    # ── result.website_results 中的 blog 条目 ─────────────────────
    print()
    print("=" * 60)
    print("  result.website_results (post dedup) — blog items")
    print("=" * 60)
    all_blog = [i for i in result.website_results if i.source_channel == "website_blog"]
    blog_in_win = [i for i in all_blog if i.within_window]
    blog_out_win = [i for i in all_blog if not i.within_window]
    print(f"  total blog in result.website_results: {len(all_blog)}")
    print(f"  within_window=True:  {len(blog_in_win)}")
    print(f"  within_window=False: {len(blog_out_win)}")

    if blog_in_win:
        print()
        print("  [IN-WINDOW BLOG RECORDS]")
        for i, item in enumerate(blog_in_win, 1):
            is_search = getattr(item, "brave_search_relevance", "N/A")
            score = getattr(item, "brave_search_score", "N/A")
            reason = getattr(item, "brave_search_reason", "N/A")
            print(f"\n  [{i}] TITLE:         {item.update_title or '—'}")
            print(f"       URL:           {item.source_url or '—'}")
            print(f"       published_at:  {item.published_at or '—'}")
            print(f"       update_date:   {item.update_date or '—'}")
            print(f"       source_channel:{item.source_channel or '—'}")
            print(f"       within_window: {item.within_window}")
            print(f"       update_status: {item.update_status or '—'}")
            print(f"       is_entry_page: {getattr(item, 'is_entry_page', '—')}")
            print(f"       is_search_related: {is_search}")
            print(f"       search_score:      {score}")
            print(f"       search_reason:     {reason}")
    else:
        print()
        print("  [!] result.website_results 中无 within_window=True 的 blog 条目")

    # ── filter_valid_results 结果 ─────────────────────────────────
    print()
    print("=" * 60)
    print("  filter_valid_results() 输出")
    print("=" * 60)
    fr = filter_valid_results(
        result.website_results,
        result.github_results,
        window_start=args.start_date,
        window_end=args.end_date,
    )
    print(f"  blog_valid:   {len(fr.blog_valid)}")
    print(f"  docs_valid:   {len(fr.docs_valid)}")
    print(f"  docs_pending: {len(fr.docs_pending)}")
    print(f"  github_valid: {len(fr.github_valid)}")
    print(f"  outside_window: {len(fr.outside_window)}")

    if fr.blog_valid:
        print()
        print("  [BLOG_VALID ITEMS]")
        for i, item in enumerate(fr.blog_valid, 1):
            print(f"  [{i}] {item.update_title} | {item.published_at} | {item.source_url}")
    else:
        print()
        print("  [!] fr.blog_valid = 0")

    # ── debug_items 中的 blog 分桶 ────────────────────────────────
    print()
    print("=" * 60)
    print("  debug_items — blog channel 分桶明细")
    print("=" * 60)
    blog_dbg = [d for d in fr.debug_items if d.source_channel == "website_blog"]
    print(f"  total blog debug items: {len(blog_dbg)}")
    for d in blog_dbg:
        print(f"  bucket={d.bucket:<20s} in_window={str(d.within_window):<6} "
              f"published_at={d.published_at or '—':20s} title={d.title[:50]}")

    # ── 重点：Place Search 文章检测 ───────────────────────────────
    print()
    print("=" * 60)
    print('  重点核验："Place Search" / "place-search" 文章')
    print("=" * 60)
    place_keywords = ["place search", "place-search", "google maps", "6–7x", "alternative"]
    found_place = False
    # 检查 result.website_results
    for item in result.website_results:
        combined = f"{(item.update_title or '').lower()} {(item.source_url or '').lower()}"
        if any(kw.lower() in combined for kw in place_keywords):
            found_place = True
            is_search = getattr(item, "brave_search_relevance", "N/A")
            print(f"  FOUND in website_results:")
            print(f"    title:        {item.update_title}")
            print(f"    url:          {item.source_url}")
            print(f"    published_at: {item.published_at}")
            print(f"    within_window:{item.within_window}")
            print(f"    is_search:    {is_search}")

    if not found_place:
        print("  NOT in result.website_results")
        # 检查是否在原始 blog_items 里被 Search 过滤器过滤掉
        # 无法直接访问 blog_items，但可以检查 debug 信息
        print("  (该文章可能在 Brave Search relevance filter 前就被/blog/ URL 过滤)")
        print("  URL 模式检测: brave.com/blog/place-search* 应含 /blog/ 路径 → 应能被发现")
        print("  实际 URL 格式待确认（可能是 /category/brave-search-news/ 路径）")

    # ── 错误信息 ──────────────────────────────────────────────────
    if result.errors:
        print()
        print("=" * 60)
        print(f"  巡检错误 ({len(result.errors)} 条)")
        print("=" * 60)
        for e in result.errors:
            print(f"  [{e.get('source_type','?')}] {e.get('error','')[:150]}")


if __name__ == "__main__":
    main()
