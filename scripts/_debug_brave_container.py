import sys, os, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import requests
from bs4 import BeautifulSoup
from urllib.parse import urlparse, urljoin

url = 'https://brave.com/category/brave-search-news/'
r = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'}, timeout=20)
soup = BeautifulSoup(r.text, 'html.parser')

# Strategy 1: limit=50 only picks li/article. But on this page, article tags come AFTER
# the first 50 li (nav) items. Let's check total counts.
all_articles = soup.find_all('article')
all_li = soup.find_all('li')
print('Total <article> tags in page:', len(all_articles))
print('Total <li> tags in page:', len(all_li))

# Strategy 1 uses limit=50 combined for article+li.
# If there are 50+ <li> nav items before the <article> items, articles never get processed!
domain = urlparse(url).scheme + '://' + urlparse(url).netloc

# Count <li> before first <article>
li_before_article = 0
found_article = False
for tag in soup.find_all(['article', 'li']):
    if tag.name == 'article':
        found_article = True
        break
    li_before_article += 1

print('li tags before first article:', li_before_article)
print('articles would be included in limit=50?', li_before_article < 50)

# Show the articles
print()
print('=== Articles with blog hrefs ===')
for art in all_articles[:3]:
    a = art.find('a', href=True)
    if not a:
        continue
    href = a.get('href', '')
    full_url = href if href.startswith('http') else urljoin(domain, href)
    has_blog = '/blog/' in full_url
    # date in <p>
    date_p = ''
    for p in art.find_all('p'):
        pt = p.get_text(strip=True)
        from services.source_drilldown import _parse_blog_card_date
        cand, _ = _parse_blog_card_date(pt, '2026-07-15')
        if cand:
            date_p = cand
            break
    h2 = art.find(['h1','h2','h3','h4'])
    title = h2.get_text(strip=True) if h2 else ''
    print('container: article  href:', full_url[:60])
    print('  title:', title[:60])
    print('  has_blog:', has_blog)
    print('  date_p:', date_p)
    print()
