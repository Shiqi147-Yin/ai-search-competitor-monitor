import sys
sys.path.insert(0, ".")
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

from services.url_fetcher import fetch_url
from services.source_detector import detect_both
from services.source_capability_classifier import classify_fetch_result, get_fetch_strategy
from services.github_fetcher import fetch_github
from services.github_url_parser import parse_github_url

tests = [
    ("GitHub commits", "https://github.com/tavily-ai/tavily-mcp/commits/main/?since=2026-07-08&until=2026-07-16"),
    ("X ExaDevelopers", "https://x.com/ExaDevelopers/status/2077438984775733583"),
    ("Brave Blog", "https://brave.com/blog/place-search-improved/"),
]

for label, url in tests:
    print(f"\n{'='*60}")
    print(f"[{label}] {url[:70]}")
    detected = detect_both(url)
    platform = detected["source_platform"]
    strategy = get_fetch_strategy(platform)

    if platform == "GitHub":
        r = fetch_github(url)
        title = r.title
        status = r.status
        error = r.error
        commits = getattr(r, "commits", [])
    else:
        r = fetch_url(url)
        title = r.title
        status = r.status
        error = r.error

    cap = classify_fetch_result(
        fetch_status=status,
        has_title=bool(title),
        has_description=False,
        has_published_date=False,
        source_platform=platform,
    )

    print(f"  competitor:       {detected['competitor']}")
    print(f"  source_platform:  {platform}")
    print(f"  fetch_strategy:   {strategy}")
    print(f"  fetch_status:     {status}")
    print(f"  title:            {(title or '')[:80]}")
    if error:
        print(f"  error:            {error[:80]}")
    print(f"  needs_manual:     {cap.needs_manual}")
    print(f"  automation_level: {cap.automation_level}")
    if platform == "GitHub" and commits:
        print(f"  commits found:    {len(commits)}")
        for c in commits[:2]:
            print(f"    - {c.date} {c.sha} {c.title[:50]}")
