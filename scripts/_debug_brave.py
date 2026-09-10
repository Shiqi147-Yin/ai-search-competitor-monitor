"""Debug: check Brave raw GitHub and Blog sources."""
import sys
sys.path.insert(0, '.')
from services.official_source_monitor import load_monitoring_config
from services.github_monitor import run_github_monitor
from services.source_drilldown import drilldown_blog

config = load_monitoring_config()
brave = config.get("Brave", {})
github_config = brave.get("github", {})
website_config = brave.get("website", {})

print("=== GitHub commits ===")
gh = run_github_monitor("Brave", github_config, "2026-07-27", "2026-08-11")
print(f"commits: {len(gh.get('commits', []))}")
print(f"releases: {len(gh.get('releases', []))}")
print(f"errors: {gh.get('errors', [])}")
for c in gh.get("commits", []):
    print(f"  [{c.commit_date}] {c.commit_title[:80]}")

print("\n=== Blog drilldown ===")
blog_urls = website_config.get("blog", [])
for url in blog_urls:
    result = drilldown_blog(url, "2026-07-27", "2026-08-11")
    print(f"blog {url}: status={result.drilldown_status} items={len(result.discovered_items)}")
    for item in result.discovered_items[:5]:
        print(f"  in_win={item.within_window} date={item.published_date} {item.source_url[:80]}")
