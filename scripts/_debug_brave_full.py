"""Debug: trace Brave Blog through full normalize_all pipeline."""
import sys
sys.path.insert(0, '.')
from services.official_source_monitor import run_official_monitor

result = run_official_monitor(
    competitor="Brave",
    window_start="2026-07-01",
    window_end="2026-08-11",
    source_types=["blog"],
    enable_querit_supplement=False,
)

print(f"website_results: {len(result.website_results)}")
print(f"errors: {result.errors}")
for item in result.website_results:
    print(f"  channel={item.source_channel} in_win={item.within_window} "
          f"pub={item.published_at!r} url={item.source_url[:80]}")
