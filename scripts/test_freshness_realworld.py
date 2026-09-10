import sys, io
sys.path.insert(0, ".")
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
from env_loader import load_env; load_env()
from services.querit_client import search
from services.freshness_filter import check_freshness, freshness_summary
from datetime import datetime, timezone

ref = datetime.now(timezone.utc)
result = search("Latest Tavily product updates from the past 7 days", 10)
print(f"success={result.success}, results={len(result.results)}, source_path={result.source_path}")

freshnesslist = []
for r in result.results:
    rec = {
        "page_age": r.published_date,
        "published_date": r.published_date,
        "source_url": r.url,
        "title": r.title,
    }
    fr = check_freshness(rec, 7, ref)
    freshnesslist.append(fr)
    date_str = (r.published_date or "-")[:10]
    print(f"  [{fr.freshness_status[:12]}] {date_str} | {r.title[:55]}")

stats = freshness_summary(freshnesslist)
print()
print("新鲜度统计:", stats)
