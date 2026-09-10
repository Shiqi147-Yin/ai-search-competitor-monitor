import sys, io
sys.path.insert(0, ".")
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
from env_loader import load_env; load_env()
from services.querit_client import search
from services.querit_result_adapter import adapt_result
from services.freshness_filter import check_freshness
from datetime import datetime, timezone

ref = datetime.now(timezone.utc)
result = search("Latest Tavily product updates from the past 7 days", 10)
print(f"success={result.success}, results={len(result.results)}, path={result.source_path}")

stats = {"with_date": 0, "no_date": 0, "within": 0, "outside": 0, "missing": 0}
for r in result.results:
    rec = adapt_result(r, "diag", 1, "Tavily")
    if rec is None:
        continue
    has_date = bool(rec.get("published_date"))
    if has_date:
        stats["with_date"] += 1
    else:
        stats["no_date"] += 1
    fr = check_freshness(rec, 7, ref)
    if fr.freshness_status == "within_window":
        stats["within"] += 1
    elif fr.freshness_status == "outside_window":
        stats["outside"] += 1
    else:
        stats["missing"] += 1
    d = (rec.get("published_date") or "")[:10]
    status = fr.freshness_status[:12]
    title_short = (r.title or "")[:50]
    print(f"  [{status}] {d} | {title_short}")

print()
print("统计:", stats)
