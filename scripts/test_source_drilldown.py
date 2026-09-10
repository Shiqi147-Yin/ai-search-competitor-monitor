"""下钻测试脚本（不写正式数据库）
用法：
  python scripts/test_source_drilldown.py --url "https://www.tavily.com/blog" --days 14
  python scripts/test_source_drilldown.py --url "https://github.com/tavily-ai/tavily-mcp" --days 14
"""
import sys
import io
import argparse
from pathlib import Path
from datetime import datetime, timezone, timedelta

sys.path.insert(0, str(Path(__file__).parent.parent))
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

from env_loader import load_env
load_env()

from services.page_type_classifier import classify_page_type, is_entry_page, is_import_eligible
from services.source_drilldown import drilldown_result


def main():
    parser = argparse.ArgumentParser(description="入口页下钻测试")
    parser.add_argument("--url", required=True, help="目标 URL")
    parser.add_argument("--days", type=int, default=14, help="时间窗口天数")
    args = parser.parse_args()

    url = args.url.strip()
    now = datetime.now(timezone.utc)
    window_start = (now - timedelta(days=args.days)).strftime("%Y-%m-%dT%H:%M:%SZ")
    window_end = now.strftime("%Y-%m-%dT%H:%M:%SZ")

    print(f"\n=== 下钻测试 ===")
    print(f"URL: {url}")
    print(f"时间窗口: {window_start[:10]} 至 {window_end[:10]}")
    print()

    pt = classify_page_type(url)
    entry = is_entry_page(pt)
    eligible = is_import_eligible(pt)

    print(f"page_type:      {pt}")
    print(f"is_entry_page:  {entry}")
    print(f"import_eligible:{eligible}")
    print()

    if not entry:
        print("该页面不是入口页，无需下钻。")
        return

    print("执行下钻...")
    rec = {"source_url": url, "page_type": pt}
    result = drilldown_result(rec, window_start, window_end)

    print(f"drilldown_status: {result.drilldown_status}")
    if result.error:
        print(f"error: {result.error}")
    print(f"发现结果数: {len(result.discovered_items)}")
    print()

    for i, item in enumerate(result.discovered_items):
        win_flag = "✅" if item.within_window else "❌"
        effective_date = item.published_date or item.updated_at or ""
        date_source = "published_at" if item.published_date else ("updated_at(sitemap)" if item.updated_at else "none")
        freshness = "within_window" if item.within_window else ("outside_window" if effective_date else "date_missing")
        print(f"  [{i+1}] {win_flag} [{item.page_type}] {item.title[:60]}")
        print(f"       URL:             {item.source_url[:80]}")
        if item.published_date:
            print(f"       published_at:    {item.published_date}")
        if item.updated_at:
            print(f"       updated_at:      {item.updated_at}")
        print(f"       effective_date:  {effective_date[:20] or '(none)'}")
        print(f"       date_source:     {date_source}")
        print(f"       freshness_status:{freshness}")
        print(f"       import_eligible: {item.import_eligible}  discovery: {item.discovery_method}")
        print()

    within = sum(1 for it in result.discovered_items if it.within_window)
    print(f"窗口内: {within}/{len(result.discovered_items)}")


if __name__ == "__main__":
    main()
