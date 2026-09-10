"""Debug script to diagnose github_monitor mock patching."""
from unittest.mock import patch

ATOM_COMMITS = """<?xml version="1.0" encoding="UTF-8"?>
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


def side_effect(url, accept="application/json"):
    print(f"  _get called: url={url!r}")
    if "atom" in url:
        return 200, ATOM_COMMITS
    return 404, ""


import services.github_monitor as gm

with patch.object(gm, "_get", side_effect=side_effect):
    commits = gm.monitor_repo_commits("tavily-ai", "tavily-mcp", "2026-07-08", "2026-07-17")
    print(f"commits found: {len(commits)}")
    for c in commits:
        print(f"  {c.commit_date}  {c.commit_title}")
