import sys, os, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import requests
from bs4 import BeautifulSoup

UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124.0.0.0 Safari/537.36'
TIMEOUT = (10, 20)

def get(url, accept='text/html'):
    try:
        r = requests.get(url, headers={'User-Agent': UA, 'Accept': accept}, timeout=TIMEOUT, allow_redirects=True)
        return r.status_code, r.text
    except Exception as e:
        return -1, str(e)[:120]

# Extract all search/api related URLs from brave.com sitemap
print('=== brave.com sitemap Search-API related URLs ===')
code, body = get('https://brave.com/en/sitemap.xml', accept='application/xml')
print(f'sitemap HTTP: {code}')

# Parse all URLs from sitemap
import xml.etree.ElementTree as ET
all_urls = []
try:
    root = ET.fromstring(body)
    ns = {'sm': 'http://www.sitemaps.org/schemas/sitemap/0.9'}
    all_urls = [loc.text for loc in root.findall('.//sm:loc', ns) if loc.text]
except Exception as e:
    print('XML parse error:', e)
    # Fallback: regex
    import re
    all_urls = re.findall(r'<loc>(.*?)</loc>', body)

print(f'Total URLs in sitemap: {len(all_urls)}')

# Filter Search API related
search_api_urls = [u for u in all_urls if any(kw in u.lower() for kw in [
    '/search/api/', '/search-api', 'brave-search-api', '/learn/best-search',
    'brave-search-api-', 'search-api-', '/glossary/', '/guides/'
]) and 'brave.com' in u]

print(f'Search API related: {len(search_api_urls)}')
print()

# Sample first 20
for u in search_api_urls[:20]:
    print(f'  {u}')

print()
# Check if these pages are actually accessible and contain docs-like content
print('=== Accessibility check for top 5 search/api pages ===')
from services.brave_search_relevance import classify_brave_search_relevance
accessible_docs = []
for url in search_api_urls[:10]:
    dc, db = get(url)
    if dc == 200:
        # Check if it looks like docs/guides content
        soup = BeautifulSoup(db, 'html.parser')
        title = (soup.find('title') or soup.find('h1') or soup.find('h2'))
        title_text = title.get_text(strip=True)[:80] if title else '—'
        rel = classify_brave_search_relevance(title=title_text, url=url)
        accessible_docs.append({'url': url, 'title': title_text, 'is_search': rel.is_search_related})
        print(f'  OK  is_search={rel.is_search_related} [{title_text[:60]}]')
        print(f'      {url}')
    else:
        print(f'  {dc}  {url}')
print()
print(f'Accessible Search-related pages: {len([d for d in accessible_docs if d["is_search"]])}')
