"""Debug: check why Brave Blog shows in_window=0."""
import sys, requests, re
sys.path.insert(0, '.')
from services.source_drilldown import drilldown_blog, _within_window, _parse_blog_card_date

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
r = requests.get("https://brave.com/blog", headers={"User-Agent": UA}, timeout=20)
print(f"Blog HTTP {r.status_code}, size={len(r.text)}")

# Find all /blog/ article links with surrounding text
from bs4 import BeautifulSoup
soup = BeautifulSoup(r.text, "html.parser")

# Check article/li containers
articles = soup.find_all(["article", "li"], limit=20)
print(f"\n<article>/<li> count: {len(articles)}")
for a in articles[:3]:
    print(f"  {str(a)[:200]}")

# Find /blog/ hrefs
links = [a.get("href", "") for a in soup.find_all("a", href=True) if "/blog/" in a.get("href", "")]
print(f"\n/blog/ links found: {len(links)}")
for link in links[:10]:
    text = soup.find("a", href=link)
    if text:
        raw_text = text.get_text(separator=" ", strip=True)[:150]
        date, clean_title = _parse_blog_card_date(raw_text, "2026-08-11")
        print(f"  link={link}")
        print(f"  raw_text={raw_text[:80]}")
        print(f"  parsed_date={date}")
