"""Debug: check why tavily-mcp Research streaming/timeout is now MISS."""
import sys
sys.path.insert(0, '.')

from services.official_source_monitor import run_official_monitor
from services.github_event_aggregator import aggregate_commits
from services.github_monitor import run_github_monitor, GitHubCommitRecord
from services.github_relevance_scorer import filter_events_by_relevance, classify_github_event_relevance
from services.official_source_monitor import load_monitoring_config

config = load_monitoring_config()
tavily_config = config.get("Tavily", {})
github_config = tavily_config.get("github", {})
kw_config = tavily_config.get("relevance_keywords", None)

print("=== Tavily GitHub raw commits ===")
gh = run_github_monitor("Tavily", github_config, "2026-07-08", "2026-07-17")
for c in gh.get("commits", []):
    print(f"  [{c.commit_date}] {c.commit_title[:80]}")

print("\n=== After aggregate_commits ===")
events = aggregate_commits(gh.get("commits", []))
for e in events:
    print(f"  [{e.start_date}] {e.event_title[:80]} is_release={e.is_release}")

print("\n=== After filter_events_by_relevance ===")
primary, diagnostic = filter_events_by_relevance(events, config_keywords=kw_config)
print(f"primary={len(primary)}, diagnostic={len(diagnostic)}")
for e in primary:
    print(f"  PRIMARY: {e.event_title[:80]}")
    print(f"    relevance={getattr(e,'github_relevance','?')} score={getattr(e,'github_relevance_score',0):.2f}")
for e in diagnostic:
    print(f"  DIAG: {e.event_title[:60]} | {getattr(e,'github_relevance','?')}")
