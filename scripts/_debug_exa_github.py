"""Debug: trace Exa GitHub events through V3 aggregator and relevance filter."""
import sys
sys.path.insert(0, '.')

from services.official_source_monitor import load_monitoring_config
from services.github_monitor import run_github_monitor
from services.github_event_aggregator import aggregate_commits, _classify_topic
from services.github_relevance_scorer import filter_events_by_relevance

config = load_monitoring_config()
exa_config = config.get("Exa", {})
github_config = exa_config.get("github", {})
kw_config = exa_config.get("relevance_keywords", None)

window_start = "2026-07-27"
window_end   = "2026-08-10"

gh_result = run_github_monitor("Exa", github_config, window_start, window_end)
raw_commits = gh_result.get("commits", [])
raw_releases = gh_result.get("releases", [])

print(f"Raw commits: {len(raw_commits)}")
print(f"Raw releases: {len(raw_releases)}")

print("\n=== Topic grouping ===")
from collections import defaultdict
by_topic = defaultdict(list)
for c in raw_commits:
    topic = _classify_topic(c.commit_title)
    by_topic[topic].append(c)
for topic, items in sorted(by_topic.items()):
    print(f"  {topic}: {len(items)}")
    for c in items:
        print(f"    [{c.commit_date}] {c.commit_title[:80]}")

print("\n=== After aggregate_commits ===")
events = aggregate_commits(raw_commits)
print(f"Total aggregated events: {len(events)}")
for e in events:
    print(f"  [{e.start_date}] topic={e.topic} | {e.event_title[:80]}")
    print(f"    commits={e.commit_count} is_release={e.is_release} urls={len(e.commit_urls)}")

print("\n=== After filter_events_by_relevance ===")
primary, diagnostic = filter_events_by_relevance(events, config_keywords=kw_config)
print(f"primary={len(primary)}, diagnostic={len(diagnostic)}")
print("\nFinal events (primary):")
for i, e in enumerate(primary, 1):
    print(f"  [{i}] {e.event_title}")
    print(f"       date={e.start_date} commits={e.commit_count}")
    print(f"       evidence: {e.commit_urls[:2]}")
print("\nDiagnostic (filtered):")
for e in diagnostic:
    print(f"  - {e.event_title[:60]} | topic={getattr(e,'topic','?')} | relevance={getattr(e,'github_relevance','?')}")

