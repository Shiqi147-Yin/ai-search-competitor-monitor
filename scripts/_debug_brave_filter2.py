"""Debug: trace filter_valid_results with Brave OfficialUpdateItems."""
import sys
sys.path.insert(0, '.')
from services.official_source_monitor import run_official_monitor
from services.official_monitor_importer import filter_valid_results

result = run_official_monitor(
    competitor="Brave",
    window_start="2026-07-01",
    window_end="2026-08-11",
    source_types=["blog"],
    enable_querit_supplement=False,
)

print(f"website_results: {len(result.website_results)}")
in_win = [i for i in result.website_results if i.within_window]
print(f"within_window=True: {len(in_win)}")

# Now filter
fr = filter_valid_results(
    result.website_results,
    [],
    window_start="2026-07-01",
    window_end="2026-08-11",
)
print(f"\nblog_valid: {len(fr.blog_valid)}")
print(f"outside_window: {len(fr.outside_window)}")
for item in fr.blog_valid:
    print(f"  VALID: {item.published_at!r} {item.source_url[:80]}")
