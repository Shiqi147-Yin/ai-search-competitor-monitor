"""Debug: full drilldown_blog trace for Brave."""
import sys
sys.path.insert(0, '.')
from services.source_drilldown import drilldown_blog

result = drilldown_blog("https://brave.com/blog", "2026-07-01", "2026-08-11")
print(f"status: {result.drilldown_status}, total items: {len(result.discovered_items)}")
for item in result.discovered_items:
    print(f"  in_win={item.within_window} date={item.published_date!r} url={item.source_url[:80]}")
