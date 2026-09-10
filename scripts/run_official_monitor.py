"""CLI 运行脚本：官方来源主动巡检
用法：
    python scripts/run_official_monitor.py \
        --competitor Tavily \
        --start-date 2026-07-08 \
        --end-date 2026-07-17 \
        --sources all \
        --disable-querit-supplement

默认不写正式看板，仅打印巡检结果。
"""
import argparse
import sys
import os

# 确保项目根目录在 path 中
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from services.official_source_monitor import run_official_monitor


_HUMAN_BENCHMARKS = {
    "Tavily": [
        {
            "name": "Keyless Search Blog",
            "keywords": ["keyless", "keyless search"],
            "channel": "website_blog",
        },
        {
            "name": "Nemo Deep Agents",
            "keywords": ["nemo", "nvidia nemo", "deep agents"],
            "channel": "",  # docs/integration 均可，不限频道
        },
        {
            "name": "tavily-mcp Research streaming/timeout",
            "keywords": ["streaming", "timeout", "research", "0.2.21", "stream pipeline"],
            "channel": "",  # synthesizer 可能会改变 source_channel，不限制
            "min_matches": 2,  # 至少 2 个关键词命中，防止单个通用词误匹配
        },
    ]
}


def _check_benchmark(result, competitor: str) -> list[dict]:
    """检查人工基准命中情况。匹配最多关键词的 candidate 优先。"""
    benchmarks = _HUMAN_BENCHMARKS.get(competitor, [])
    hits = []
    all_items = list(result.website_results) + list(result.github_results)

    for bm in benchmarks:
        best_match = None
        best_score = 0
        channel_filter = bm.get("channel", "")
        min_matches = bm.get("min_matches", 1)

        for item in all_items:
            if channel_filter and item.source_channel != channel_filter:
                continue
            title_lower = (item.update_title or "").lower()
            url_lower = (item.source_url or "").lower()
            combined = title_lower + " " + url_lower
            match_count = sum(1 for kw in bm["keywords"] if kw in combined)
            if match_count >= min_matches and match_count > best_score:
                best_score = match_count
                best_match = item

        hits.append({
            "name": bm["name"],
            "hit": best_match is not None,
            "item": best_match,
        })
    return hits


def _print_section(title: str, items: list, fields: list[str]) -> None:
    print(f"\n{'='*60}")
    print(f"  {title}  ({len(items)} 条)")
    print(f"{'='*60}")
    if not items:
        print("  （无）")
        return
    for i, item in enumerate(items, 1):
        print(f"\n  [{i}]", end="")
        for f in fields:
            val = getattr(item, f, "") or ""
            if val:
                print(f"  {f}: {val}", end="")
        print()
        # 显示 evidence_urls
        urls = getattr(item, "evidence_urls", [])
        if urls:
            for u in urls[:3]:
                print(f"       URL: {u}")


def main():
    parser = argparse.ArgumentParser(description="官方来源主动巡检")
    parser.add_argument("--competitor", default="Tavily")
    parser.add_argument("--start-date", required=True)
    parser.add_argument("--end-date", required=True)
    parser.add_argument("--sources", default="all",
                        help="all / blog / docs / integrations / github（逗号分隔）")
    parser.add_argument("--disable-querit-supplement", action="store_true")
    parser.add_argument("--show-outside-window", action="store_true",
                        help="显示窗口外结果（默认关闭，只显示窗口内有效更新）")
    args = parser.parse_args()

    source_types = [s.strip() for s in args.sources.split(",")]
    enable_querit = not args.disable_querit_supplement

    print(f"\n>>> 官方来源主动巡检")
    print(f"    竞品: {args.competitor}")
    print(f"    时间窗口: {args.start_date} ~ {args.end_date}")
    print(f"    来源: {source_types}")
    print(f"    Querit 补充: {'开启' if enable_querit else '关闭'}")

    result = run_official_monitor(
        competitor=args.competitor,
        window_start=args.start_date,
        window_end=args.end_date,
        source_types=source_types,
        enable_querit_supplement=enable_querit,
    )

    # ── Blog 更新 ────────────────────────────────────────────────
    all_blog = [i for i in result.website_results if i.source_channel == "website_blog"]
    blog_valid = [i for i in all_blog if i.within_window]
    blog_outside = [i for i in all_blog if not i.within_window]

    if args.show_outside_window:
        _print_section("Blog 更新（全部）", all_blog,
                       ["update_title", "published_at", "update_status", "within_window"])
    else:
        _print_section("Blog 更新（窗口内）", blog_valid,
                       ["update_title", "published_at", "update_status"])
        if blog_outside:
            print(f"\n  [窗口外 Blog] {len(blog_outside)} 条（使用 --show-outside-window 查看）")

    # ── Docs 有效更新（new_page + substantive_update）────────────
    docs_valid = [i for i in result.website_results
                  if i.source_channel in ("website_docs", "website_integration")
                  and i.update_status in ("new_page", "substantive_update")
                  and not i.is_generic_page]
    _print_section("Docs 有效更新", docs_valid,
                   ["update_title", "updated_at", "docs_page_role", "update_status"])

    # ── Docs 待确认（高价值 first_seen）──────────────────────────
    docs_pending = [i for i in result.website_results
                    if i.source_channel in ("website_docs", "website_integration")
                    and i.update_status == "first_seen"
                    and not i.is_generic_page]
    # 首次运行 new_page 也列入待确认
    docs_first_seen = [i for i in result.website_results
                       if i.source_channel in ("website_docs", "website_integration")
                       and i.update_status == "new_page"
                       and not i.is_generic_page
                       and i not in docs_valid]
    docs_confirm = docs_pending + docs_first_seen
    _print_section("Docs 待确认（首次发现 / 高价值）", docs_confirm,
                   ["update_title", "updated_at", "docs_page_role"])

    # ── GitHub 业务事件（synthesizer 输出）──────────────────────
    # github_results 现在包含 business events，releases 已合并进去
    github_events = result.github_results  # all = final business events
    synthesis_methods = {getattr(i, "synthesis_method", "deterministic") for i in github_events}
    synthesis_label = "mock_llm_synthesis" if "mock_llm_synthesis" in synthesis_methods else "deterministic"
    _print_section(f"GitHub 业务事件 [synthesis={synthesis_label}]", github_events,
                   ["update_title", "update_date", "category", "importance"])

    # ── Querit 补充 ──────────────────────────────────────────────
    if result.querit_supplement_results:
        _print_section("Querit 补充线索", result.querit_supplement_results,
                       ["update_title", "update_date", "source_channel"])

    # ── 错误 ─────────────────────────────────────────────────────
    if result.errors:
        print(f"\n{'='*60}")
        print(f"  巡检错误  ({len(result.errors)} 条)")
        print(f"{'='*60}")
        for e in result.errors:
            print(f"  [{e.get('source_type','?')}] {e.get('error','')[:120]}")

    # ── 来源统计 ─────────────────────────────────────────────────
    if result.source_stats:
        print(f"\n{'='*60}")
        print("  来源统计")
        print(f"{'='*60}")
        for src, stat in result.source_stats.items():
            if src == "brave_search_filter":
                # 专用键：scanned/search_related/filtered_non_search
                print(
                    f"  {src:25s}  "
                    f"input={stat.get('scanned',0)}, "
                    f"kept={stat.get('search_related',0)}, "
                    f"filtered={stat.get('filtered_non_search',0)}"
                )
            elif src == "blog_funnel":
                # Brave 专属 Blog 漏斗（只含 Blog，不含 Docs）
                print(f"\n  Blog 抓取漏斗（Brave Search · Blog only）:")
                print(f"    discovered      = {stat.get('blog_discovered',0)}")
                print(f"    search_related  = {stat.get('blog_search_related',0)}")
                print(f"    non_search_filt = {stat.get('blog_non_search_filtered',0)}")
                print(f"    in_window       = {stat.get('blog_in_window',0)}")
                print(f"    outside_window  = {stat.get('blog_outside_window',0)}")
                print(f"    invalid_date    = {stat.get('blog_invalid_date',0)}")
            elif src == "docs_funnel":
                # Brave 专属 Docs 漏斗（区分 confirmed / pending）
                print(f"\n  Docs 抓取漏斗（Brave Search · Docs only）:")
                print(f"    discovered      = {stat.get('docs_discovered',0)}")
                print(f"    search_related  = {stat.get('docs_search_related',0)}")
                print(f"    non_search_filt = {stat.get('docs_non_search_filtered',0)}")
                print(f"    in_window       = {stat.get('docs_in_window',0)}  (date_source={stat.get('docs_date_source','—')})")
                print(f"    ├─ confirmed     = {stat.get('docs_confirmed',0)}")
                print(f"    ├─ pending       = {stat.get('docs_pending',0)}")
                print(f"    ├─ outside_window= {stat.get('docs_outside_window',0)}")
                print(f"    └─ date_unknown  = {stat.get('docs_date_unknown',0)}")
            elif src == "docs":
                # Docs 诊断完整输出
                ds = stat.get("docs_status", "—")
                entry = stat.get("docs_entry_url", "—")
                sitemap = stat.get("docs_sitemap_url", "—")
                reason = stat.get("docs_empty_reason", "")
                print(f"  {src:25s}  found={stat.get('found',0)}, in_window={stat.get('in_window',0)}")
                print(f"  {'':25s}  docs_entry_url     = {entry}")
                print(f"  {'':25s}  docs_sitemap_url   = {sitemap}")
                print(f"  {'':25s}  docs_status        = {ds}")
                if reason:
                    print(f"  {'':25s}  docs_empty_reason  = {reason}")
            elif src == "querit_supplement":
                print(f"  {src:25s}  found={stat.get('querit_found',0)}, "
                      f"new={stat.get('querit_new',0)}, "
                      f"duplicate={stat.get('querit_duplicate',0)}")
            else:
                parts = [f"found={stat.get('found',0)}", f"in_window={stat.get('in_window',0)}"]
                if "aggregated_events" in stat:
                    parts.append(f"events={stat['aggregated_events']}")
                if "docs_status" in stat:
                    parts.append(f"docs_status={stat['docs_status']}")
                if "github_status" in stat:
                    parts.append(f"github_status={stat['github_status']}")
                print(f"  {src:25s}  {', '.join(parts)}")

    # ── 人工基准验收 ─────────────────────────────────────────────
    print(f"\n{'='*60}")
    print("  人工基准命中情况")
    print(f"{'='*60}")
    benchmarks = _check_benchmark(result, args.competitor)
    for bm in benchmarks:
        status = "[HIT]" if bm["hit"] else "[MISS]"
        print(f"  {status}  {bm['name']}")
        if bm["hit"]:
            item = bm["item"]
            print(f"         标题: {item.update_title}")
            print(f"         日期: {item.update_date or item.published_at or item.updated_at}")
            print(f"         来源: {item.source_channel}")
            if item.source_url:
                print(f"         URL: {item.source_url}")

    hit_count = sum(1 for bm in benchmarks if bm["hit"])
    total = len(benchmarks)
    print(f"\n  基准命中率: {hit_count}/{total}")
    if hit_count >= 2:
        print("  >>> 达到最低验收目标（≥2/3）")
    if hit_count == 3:
        print("  >>> 达到理想验收目标（3/3）")

    print(f"\n  巡检完成: {result.completed_at}")
    print()


if __name__ == "__main__":
    main()
