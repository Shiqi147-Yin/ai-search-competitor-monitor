"""Debug: check if Nemo appears in integration results."""
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

print(f"website_results: {len(result.website_results)}")
for item in result.website_results:
    if "nemo" in (item.update_title or "").lower() or "nemo" in (item.source_url or "").lower():
        print(f"  NEMO FOUND: {item.source_channel} {item.update_title} {item.source_url}")
    else:
        print(f"  {item.source_channel:25s}  {item.update_title[:50]}  {item.update_status}")

print("\ngithub_results:", len(result.github_results))
print("errors:", result.errors)
