"""Debug: trace what Brave items get filtered by Search relevance."""
import sys, io
sys.path.insert(0, '.')
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

from services.official_source_monitor import load_monitoring_config
from services.brave_search_relevance import filter_brave_items_by_search_relevance
from services.official_update_normalizer import normalize_blog_item
from services.website_monitor import run_website_monitor

config = load_monitoring_config()
brave_config = config.get("Brave", {})
website_config = brave_config.get("website", {})

web_result = run_website_monitor("Brave", website_config, "2026-07-01", "2026-08-11",
                                  source_types=["all"])
blog_items = web_result.get("blog", [])
print(f"blog_items from monitor: {len(blog_items)}")

normalized = [normalize_blog_item(item, "Brave") for item in blog_items]
print(f"normalized: {len(normalized)}")

search_related, filtered_out, stats = filter_brave_items_by_search_relevance(normalized)
print(f"\nFilter stats: {stats}")
print(f"Search-related ({len(search_related)}):")
for i in search_related:
    t = (i.update_title or "")[:60].encode('ascii', 'replace').decode()
    print(f"  {t}  score={getattr(i,'brave_search_score',0):.2f}")
print(f"Filtered out ({len(filtered_out)}):")
for i in filtered_out[:10]:
    t = (i.update_title or "")[:50].encode('ascii', 'replace').decode()
    reason = getattr(i,'brave_search_reason','?')[:40]
    print(f"  {t}  [{reason}]")

