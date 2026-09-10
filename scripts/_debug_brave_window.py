"""Debug: trace _within_window for Brave blog dates."""
import sys
sys.path.insert(0, '.')
from services.source_drilldown import _within_window, _parse_blog_card_date

window_start = "2026-07-01"
window_end   = "2026-08-11"

test_cases = [
    ("2026-07-08T00:00:00Z", "Place Search July 8"),
    ("2026-07-09T00:00:00Z", "BAT Roadmap July 9"),
    ("2026-07-02T00:00:00Z", "Containers July 2"),
    ("2026-06-29T00:00:00Z", "Claude Cowork June 29"),
]
for date_str, label in test_cases:
    result = _within_window(date_str, window_start, window_end)
    print(f"  {date_str} in [{window_start}~{window_end}] = {result}  ({label})")
