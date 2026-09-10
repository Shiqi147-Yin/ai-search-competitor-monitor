"""Debug: show current Exa 11 raw records for analysis before redesign."""
import sys
sys.path.insert(0, '.')
from services.official_source_monitor import load_monitoring_config
from services.github_monitor import run_github_monitor
from services.github_event_aggregator import aggregate_commits
from services.github_relevance_scorer import filter_events_by_relevance

config = load_monitoring_config()
exa_config = config.get("Exa", {})
github_config = exa_config.get("github", {})
kw_config = exa_config.get("relevance_keywords", None)

gh = run_github_monitor("Exa", github_config, "2026-07-27", "2026-08-10")
raw = gh.get("commits", [])
print(f"Raw commits: {len(raw)}")
for i, c in enumerate(raw, 1):
    print(f"  [{i:02d}] [{c.commit_date}] {c.repository.split('/')[-1]} | {c.commit_title[:90]}")
