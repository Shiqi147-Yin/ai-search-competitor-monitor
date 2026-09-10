"""Debug: trace Brave blog through filter_valid_results."""
import sys
sys.path.insert(0, '.')
from services.website_monitor import monitor_blog
from services.official_monitor_importer import filter_valid_results

items = monitor_blog("Brave", ["https://brave.com/blog"], "2026-07-01", "2026-08-11")
print(f"monitor_blog items: {len(items)}")
in_window = [i for i in items if i.within_window]
print(f"within_window=True: {len(in_window)}")
for i in in_window:
    print(f"  {i.source_type} in_win={i.within_window} date={i.published_at!r} url={i.source_url[:80]}")

fr = filter_valid_results(items, [], window_start="2026-07-01", window_end="2026-08-11")
print(f"\nFilterResult:")
print(f"  blog_valid:     {len(fr.blog_valid)}")
print(f"  outside_window: {len(fr.outside_window)}")
for item in fr.blog_valid:
    print(f"  BLOG_VALID: {item.published_at!r} {item.source_url[:80]}")
