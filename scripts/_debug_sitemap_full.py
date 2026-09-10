"""Debug: scan ALL URLs in docs.tavily.com sitemap for nemo."""
import sys
sys.path.insert(0, '.')
import requests
import xml.etree.ElementTree as ET

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
r = requests.get("https://docs.tavily.com/sitemap.xml",
                 headers={"User-Agent": UA, "Accept": "application/xml"},
                 timeout=(10,20))
print(f"sitemap HTTP {r.status_code}, size={len(r.text)}")

root = ET.fromstring(r.text)
ns = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}
all_urls = []
for url_el in root.findall(".//sm:url", ns):
    loc = url_el.findtext("sm:loc", "", ns) or ""
    lastmod = url_el.findtext("sm:lastmod", "", ns) or ""
    all_urls.append((loc, lastmod))

print(f"Total URLs in sitemap: {len(all_urls)}")

nemos = [(loc, lastmod) for loc, lastmod in all_urls if "nemo" in loc.lower()]
print(f"\nNemo URLs found: {len(nemos)}")
for loc, lastmod in nemos:
    print(f"  {lastmod[:10]}  {loc}")

# Also show lastmod=2026-07 entries
window_entries = [(loc, lastmod) for loc, lastmod in all_urls if "2026-07" in lastmod]
print(f"\nURLs with lastmod in 2026-07: {len(window_entries)}")
for loc, lastmod in window_entries:
    print(f"  {lastmod[:10]}  {loc}")
