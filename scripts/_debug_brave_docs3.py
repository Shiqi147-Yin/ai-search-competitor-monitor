import sys, os, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import requests, xml.etree.ElementTree as ET
from bs4 import BeautifulSoup
from services.brave_search_relevance import classify_brave_search_relevance

UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124.0.0.0 Safari/537.36'
TIMEOUT = (10, 20)

def get(url, accept='text/html'):
    try:
        r = requests.get(url, headers={'User-Agent': UA, 'Accept': accept}, timeout=TIMEOUT, allow_redirects=True)
        return r.status_code, r.text
    except Exception as e:
        return -1, str(e)[:120]

# Get full list of Search-API URLs from sitemap
code, body = get('https://brave.com/en/sitemap.xml', accept='application/xml')
all_urls = []
try:
    root = ET.fromstring(body)
    ns = {'sm': 'http://www.sitemaps.org/schemas/sitemap/0.9'}
    for url_el in root.findall('.//sm:url', ns):
        loc = url_el.find('sm:loc', ns)
        lastmod = url_el.find('sm:lastmod', ns)
        if loc is not None and loc.text:
            all_urls.append((loc.text, lastmod.text if lastmod is not None else ''))
except Exception as e:
    import re
    locs = re.findall(r'<loc>(.*?)</loc>', body)
    mods = re.findall(r'<lastmod>(.*?)</lastmod>', body)
    all_urls = list(zip(locs, mods + [''] * (len(locs) - len(mods))))

# Filter strictly to /search/api/ paths (not /glossary/ which is too generic)
strict_search_api = [
    (u, lm) for u, lm in all_urls
    if '/search/api/' in u or '/search-api' in u
]

print(f'Total sitemap URLs: {len(all_urls)}')
print(f'Strict /search/api/ URLs: {len(strict_search_api)}')
print()

# Check accessibility and lastmod for all strict_search_api pages
print('=== /search/api/ pages: lastmod + accessibility ===')
accessible_search = []
for url, lastmod in strict_search_api:
    dc, db = get(url)
    if dc == 200:
        soup = BeautifulSoup(db, 'html.parser')
        title_el = soup.find('title') or soup.find('h1')
        title_text = title_el.get_text(strip=True)[:70] if title_el else '—'
        rel = classify_brave_search_relevance(title=title_text, url=url)
        accessible_search.append({
            'url': url, 'title': title_text, 'lastmod': lastmod,
            'is_search': rel.is_search_related
        })
        flag = 'SEARCH' if rel.is_search_related else '------'
        print(f'  {flag} lastmod={lastmod or "—":12s} [{title_text[:55]}]')
    else:
        print(f'  HTTP {dc:3d} lastmod={lastmod or "—":12s} {url}')

print()
print(f'Accessible: {len(accessible_search)}')
print(f'Search-related: {len([d for d in accessible_search if d["is_search"]])}')
print()

# Check lastmod dates for window 2026-07-28 ~ 2026-08-11
from services.source_drilldown import _within_window
window_start = '2026-07-28'
window_end = '2026-08-11'
in_window = [d for d in accessible_search if _within_window(d.get('lastmod',''), window_start, window_end)]
print(f'In window ({window_start} ~ {window_end}): {len(in_window)}')
for d in in_window:
    print(f'  lastmod={d["lastmod"]} {d["url"]}')
