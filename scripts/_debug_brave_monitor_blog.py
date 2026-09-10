"""Debug: find why 3 Brave blog articles show in_win=True but not reaching monitor_blog output."""
import sys
sys.path.insert(0, '.')
from services.website_monitor import monitor_blog

items = monitor_blog(
    "Brave",
    ["https://brave.com/blog"],
    "2026-07-01",
    "2026-08-11",
)
print(f"monitor_blog returned: {len(items)} items")
for i in items:
    print(f"  in_win={i.within_window} date={i.published_at!r} url={i.source_url[:80]}")
