"""Debug: check raw drilldown_docs output for integrations entry."""
import sys
sys.path.insert(0, '.')
from services.source_drilldown import drilldown_docs

result = drilldown_docs(
    "https://docs.tavily.com/documentation/integrations",
    "2026-07-08",
    "2026-07-17",
)
print(f"status: {result.drilldown_status}, items: {len(result.discovered_items)}")
nemo_found = False
for item in result.discovered_items:
    marker = " <<< NEMO" if "nemo" in (item.source_url or "").lower() else ""
    print(f"  in_win={item.within_window}  updated_at={item.updated_at}  {item.source_url[:80]}{marker}")
    if "nemo" in (item.source_url or "").lower():
        nemo_found = True
print(f"\nNemo found: {nemo_found}")
