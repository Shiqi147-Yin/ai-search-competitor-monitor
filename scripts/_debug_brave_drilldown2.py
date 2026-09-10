"""Debug: trace what drilldown_blog actually finds for brave.com/blog."""
import sys
sys.path.insert(0, '.')
from services.source_drilldown import _within_window, _parse_blog_card_date, _get, classify_page_type
from urllib.parse import urljoin, urlparse

try:
    from bs4 import BeautifulSoup as _BS
    _HAS_BS4 = True
except ImportError:
    _HAS_BS4 = False

url = "https://brave.com/blog"
window_start = "2026-07-01"
window_end = "2026-08-11"

code, html = _get(url)
print(f"HTTP {code}, size={len(html)}")

soup = _BS(html, "html.parser")
domain = "https://brave.com"

# Strategy 1: article/li containers
article_links = []
for container in soup.find_all(["article", "li"], limit=50):
    a_tag = container.find("a", href=True)
    if not a_tag:
        continue
    href = a_tag.get("href", "")
    full_url = href if href.startswith("http") else urljoin(domain, href)
    text = a_tag.get_text(separator=" ", strip=True)
    pub_date, raw_title = _parse_blog_card_date(text, window_end)
    if "/blog/" in full_url:
        article_links.append((full_url, raw_title or text[:60], pub_date))

print(f"\nStrategy 1 (article/li): {len(article_links)} /blog/ links")
for u, t, d in article_links[:10]:
    pt = classify_page_type(u, t)
    in_win = _within_window(d, window_start, window_end) if d else "no_date"
    print(f"  pt={pt} in_win={in_win} date={d!r} {u[:80]}")

# Strategy 2: bare /blog/ links
print("\nStrategy 2 (bare /blog/ links):")
for a in soup.find_all("a", href=True, limit=200):
    href = a.get("href", "")
    full_url = href if href.startswith("http") else urljoin(domain, href)
    if "/blog/" in full_url and full_url != url and full_url not in {u for u,_,_ in article_links}:
        raw_text = a.get_text(separator=" ", strip=True)
        pub_date, clean_title = _parse_blog_card_date(raw_text, window_end)
        pt = classify_page_type(full_url, clean_title)
        in_win = _within_window(pub_date, window_start, window_end) if pub_date else "no_date"
        if pt == "detail_article":
            print(f"  in_win={in_win} date={pub_date!r} {full_url[:80]}")
