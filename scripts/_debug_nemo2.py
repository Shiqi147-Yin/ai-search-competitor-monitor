"""Debug: why Nemo not found in integration results."""
import sys
sys.path.insert(0, '.')
from services.official_source_monitor import run_official_monitor

result = run_official_monitor(
    competitor="Tavily",
    window_start="2026-07-08",
    window_end="2026-07-17",
    source_types=["integrations"],
    enable_querit_supplement=False,
)

# Print all integration items with title/url
print("Total website_results:", len(result.website_results))
for item in result.website_results:
    title = (item.update_title or "").lower()
    url = (item.source_url or "").lower()
    marker = " <<< NEMO" if "nemo" in title or "nemo" in url else ""
    print(f"  [{item.docs_page_role:15s}] {item.update_title[:45]:45s}  {item.source_url[:60]}{marker}")
