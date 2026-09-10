"""Debug: check what Tavily raw commits look like."""
import sys
sys.path.insert(0, '.')
from services.official_source_monitor import load_monitoring_config
from services.github_monitor import run_github_monitor

config = load_monitoring_config()
tavily_config = config.get("Tavily", {})
github_config = tavily_config.get("github", {})

gh = run_github_monitor("Tavily", github_config, "2026-07-08", "2026-07-17")
raw = gh.get("commits", [])
rels = gh.get("releases", [])
print(f"Raw commits: {len(raw)}")
for c in raw:
    from services.github_event_aggregator import _classify_topic
    topic = _classify_topic(c.commit_title)
    print(f"  [{c.commit_date}] topic={topic} | {c.commit_title[:80]}")
print(f"\nRaw releases: {len(rels)}")
for r in rels:
    print(f"  [{r.published_at}] {r.version} {r.repository}")
