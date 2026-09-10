"""Debug: check Brave blog structure and GitHub atom feed."""
import sys, requests, re
sys.path.insert(0, '.')

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
headers = {"User-Agent": UA}

# 1. Check brave.com/blog HTML for article dates
print("=== brave.com/blog HTML analysis ===")
r = requests.get("https://brave.com/blog", headers=headers, timeout=20)
print(f"HTTP {r.status_code}, size={len(r.text)}")
# Look for /blog/ article links and dates
blog_links = re.findall(r'href="(/blog/[^"]+)"', r.text)
print(f"Found /blog/ links: {len(blog_links)}")
# Check for date patterns
date_patterns = re.findall(r'(202[0-9]-[01][0-9]-[0-3][0-9]|[A-Z][a-z]+\s+\d+,\s+202[0-9])', r.text)
print(f"Date patterns found: {date_patterns[:10]}")
print("Sample links:", blog_links[:8])

# 2. Check brave-search-skills atom feed for recent commits
print("\n=== brave-search-skills atom feed ===")
atom = requests.get(
    "https://github.com/brave/brave-search-skills/commits/main.atom",
    headers={"User-Agent": UA, "Accept": "application/atom+xml"},
    timeout=20
)
print(f"HTTP {atom.status_code}, size={len(atom.text)}")
import xml.etree.ElementTree as ET
ns = {"atom": "http://www.w3.org/2005/Atom"}
root = ET.fromstring(atom.text)
for entry in root.findall("atom:entry", ns)[:5]:
    title = entry.find("atom:title", ns)
    updated = entry.find("atom:updated", ns)
    link = entry.find("atom:link", ns)
    print(f"  [{(updated.text or '')[:10]}] {(title.text or '')[:80]}")
