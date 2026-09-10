"""Debug: check docs.tavily.com sitemap for Nemo entry."""
import sys
sys.path.insert(0, '.')
from services.source_drilldown import drilldown_docs

# Try docs root with full sitemap
result = drilldown_docs(
    "https://docs.tavily.com/",
    "2026-07-08",
    "2026-07-17",
)
print(f"status: {result.drilldown_status}, total items: {len(result.discovered_items)}")
nemo_found = False
for item in result.discovered_items:
    marker = " <<< NEMO" if "nemo" in (item.source_url or "").lower() else ""
    in_w = "IN_WIN" if item.within_window else "      "
    print(f"  {in_w}  {item.updated_at[:10]}  {item.source_url[:80]}{marker}")
    if "nemo" in (item.source_url or "").lower():
        nemo_found = True
print(f"\nNemo found in top-20: {nemo_found}")
