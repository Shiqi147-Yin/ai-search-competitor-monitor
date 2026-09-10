"""Debug: simulate exactly what the test does."""
import sys
sys.path.insert(0, '.')

from unittest.mock import patch
import services.github_monitor as gm

_ATOM_COMMITS = """<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <entry>
    <title>Add streaming support for Research tool</title>
    <author><name>alice</name></author>
    <updated>2026-07-10T12:00:00Z</updated>
    <link href="https://github.com/tavily-ai/tavily-mcp/commit/abc1234"/>
  </entry>
  <entry>
    <title>Fix timeout handling in Research</title>
    <author><name>bob</name></author>
    <updated>2026-07-10T14:00:00Z</updated>
    <link href="https://github.com/tavily-ai/tavily-mcp/commit/def5678"/>
  </entry>
  <entry>
    <title>Old commit outside window</title>
    <author><name>carol</name></author>
    <updated>2026-07-01T10:00:00Z</updated>
    <link href="https://github.com/tavily-ai/tavily-mcp/commit/old0001"/>
  </entry>
</feed>"""

# Check what _within_window returns for these dates
print("_within_window tests:")
print(" 2026-07-10T12:00:00Z:", gm._within_window("2026-07-10T12:00:00Z", "2026-07-08", "2026-07-17"))
print(" 2026-07-10:", gm._within_window("2026-07-10", "2026-07-08", "2026-07-17"))
print(" 2026-07-01:", gm._within_window("2026-07-01T10:00:00Z", "2026-07-08", "2026-07-17"))

# Parse manually
import xml.etree.ElementTree as ET
import re
ns = {"atom": "http://www.w3.org/2005/Atom"}
root = ET.fromstring(_ATOM_COMMITS)
for entry in root.findall("atom:entry", ns):
    title_el = entry.find("atom:title", ns)
    updated_el = entry.find("atom:updated", ns)
    link_el = entry.find("atom:link", ns)
    commit_date = (updated_el.text or "")[:10] if updated_el is not None else ""
    link_href = link_el.get("href", "") if link_el is not None else ""
    in_win = gm._within_window(commit_date, "2026-07-08", "2026-07-17")
    print(f"  date={commit_date!r} in_window={in_win} title={title_el.text!r}")

# Now test with real mock
def side_effect(url, accept="application/json"):
    print(f"  _get({url!r}, accept={accept!r})")
    if "atom" in url:
        return 200, _ATOM_COMMITS
    return 404, ""

with patch.object(gm, "_get", side_effect=side_effect):
    commits = gm.monitor_repo_commits("tavily-ai", "tavily-mcp", "2026-07-08", "2026-07-17")
    print(f"commits: {len(commits)}")
    for c in commits:
        print(f"  {c.commit_date} {c.commit_title}")
