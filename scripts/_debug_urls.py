"""Debug: check what URLs github_monitor._get is called with."""
import sys
sys.path.insert(0, '.')

from unittest.mock import patch, call
import services.github_monitor as gm

calls_made = []

def fake_get(url, accept="application/json"):
    calls_made.append((url, accept))
    return 404, ""

with patch.object(gm, "_get", side_effect=fake_get):
    result = gm.monitor_repo_commits("tavily-ai", "tavily-mcp", "2026-07-08", "2026-07-17")

print("URLs called:")
for u, a in calls_made:
    print(f"  {u!r}  accept={a!r}")
print(f"Commits returned: {len(result)}")
