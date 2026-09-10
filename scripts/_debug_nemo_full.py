"""Debug: trace Nemo through the full pipeline."""
import sys
sys.path.insert(0, '.')

from services.official_source_monitor import run_official_monitor
from services.official_monitor_importer import filter_valid_results

result = run_official_monitor(
    'Tavily', '2026-07-08', '2026-07-17', ['all'], False
)

print(f"website_results count: {len(result.website_results)}")
print(f"github_results count: {len(result.github_results)}")

nemo_found = False
for item in result.website_results:
    url = getattr(item, 'source_url', '') or ''
    title = (getattr(item, 'update_title', '') or '').lower()
    if 'nemo' in url.lower() or 'nemo' in title:
        nemo_found = True
        print("\n[NEMO MONITOR OUTPUT]")
        for attr in ['update_title', 'source_url', 'source_channel', 'content_type',
                     'update_status', 'published_at', 'updated_at', 'update_date',
                     'within_window', 'is_generic_page', 'docs_page_role',
                     'import_eligible', 'discovery_method']:
            print(f"  {attr} = {getattr(item, attr, 'MISSING')!r}")

if not nemo_found:
    print("\n[NEMO NOT IN website_results]")
    print("All sources:")
    for item in result.website_results:
        print(f"  {item.source_channel} | {item.update_status} | {item.docs_page_role} | {item.source_url[:60]}")

# Now filter
fr = filter_valid_results(result.website_results, result.github_results,
                          window_start='2026-07-08', window_end='2026-07-17')
print(f"\nFilterResult:")
print(f"  blog_valid:     {len(fr.blog_valid)}")
print(f"  docs_valid:     {len(fr.docs_valid)}")
print(f"  docs_pending:   {len(fr.docs_pending)}")
print(f"  github_valid:   {len(fr.github_valid)}")
print(f"  outside_window: {len(fr.outside_window)}")
print(f"  metadata_only:  {len(fr.metadata_only)}")
print(f"  generic_page:   {len(fr.generic_page)}")

# Find Nemo in debug_items
print("\n[NEMO BUCKET DEBUG]")
nemo_dbg = [d for d in fr.debug_items if 'nemo' in (d.source_url or '').lower()]
if nemo_dbg:
    for d in nemo_dbg:
        print(f"  title: {d.title}")
        print(f"  source_url: {d.source_url}")
        print(f"  source_channel: {d.source_channel}")
        print(f"  docs_page_role: {d.docs_page_role}")
        print(f"  update_status: {d.update_status}")
        print(f"  within_window: {d.within_window}")
        print(f"  is_generic_page: {d.is_generic_page}")
        print(f"  bucket: {d.bucket}")
        print(f"  drop_reason: {d.drop_reason}")
else:
    print("  Nemo not in debug_items at all!")
