import sys, os, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import requests

UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124.0.0.0 Safari/537.36'
TIMEOUT = (10, 20)

def get(url, accept='text/html'):
    try:
        r = requests.get(url, headers={'User-Agent': UA, 'Accept': accept}, timeout=TIMEOUT, allow_redirects=True)
        return r.status_code, r.text
    except Exception as e:
        return -1, str(e)[:120]

print('=== Brave Search API Docs 可访问性排查 ===')
print()

# 1. 当前配置入口
entry = 'https://api.search.brave.com/app/documentation'
code, body = get(entry)
print(f'[1] 配置入口: {entry}')
print(f'    HTTP status: {code}')
print(f'    body snippet: {body[:200]}')
print()

# 2. robots.txt
robots_url = 'https://api.search.brave.com/robots.txt'
rc, rb = get(robots_url)
print(f'[2] robots.txt: {robots_url}')
print(f'    HTTP status: {rc}')
print(f'    body: {rb[:300]}')
print()

# 3. sitemap at api.search.brave.com
sitemap1 = 'https://api.search.brave.com/sitemap.xml'
sc1, sb1 = get(sitemap1, accept='application/xml')
print(f'[3] sitemap (api.search.brave.com): {sitemap1}')
print(f'    HTTP status: {sc1}')
print(f'    body snippet: {sb1[:200]}')
print()

# 4. Brave.com sitemap (already known to have search-related URLs)
sitemap2 = 'https://brave.com/en/sitemap.xml'
sc2, sb2 = get(sitemap2, accept='application/xml')
print(f'[4] brave.com sitemap: {sitemap2}')
print(f'    HTTP status: {sc2}')
# Count search-api related URLs
search_api_urls = [ln for ln in sb2.split('\n') if 'search' in ln.lower() and ('/search/' in ln or 'api' in ln.lower() or 'documentation' in ln.lower())]
print(f'    total chars: {len(sb2)}')
print(f'    search/api related URL lines: {len(search_api_urls)}')
for u in search_api_urls[:10]:
    print(f'    -> {u.strip()[:100]}')
print()

# 5. Try known documentation detail pages
detail_pages = [
    'https://api.search.brave.com/app/documentation/web-search',
    'https://api.search.brave.com/app/documentation/web-search/query',
    'https://api.search.brave.com/app/documentation/news-search',
    'https://api.search.brave.com/app/documentation/image-search',
    'https://api.search.brave.com/app/documentation/suggest',
    'https://api.search.brave.com/app/documentation/spellcheck',
    'https://api.search.brave.com/app/documentation/local-search',
    'https://api.search.brave.com/app/documentation/video-search',
    'https://api.search.brave.com/app/documentation/rate-limits',
    'https://api.search.brave.com/app/documentation/pricing',
]
print('[5] Detail page accessibility:')
accessible = []
for url in detail_pages:
    dc, db = get(url)
    status = 'OK' if dc == 200 else f'HTTP {dc}'
    print(f'    {status:10s} {url}')
    if dc == 200:
        accessible.append(url)
print(f'    Accessible: {len(accessible)}/{len(detail_pages)}')
print()

# 6. Try alternate docs domain
alt_docs = [
    'https://brave.com/search/api/',
    'https://brave.com/search/api/documentation/',
    'https://search.brave.com/help/api',
]
print('[6] Alternate doc paths:')
for url in alt_docs:
    dc, db = get(url)
    print(f'    HTTP {dc:4d}  {url}')
    if dc == 200:
        print(f'           snippet: {db[:150]}')
