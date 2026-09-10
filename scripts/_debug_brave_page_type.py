"""Debug: check page_type_classifier for brave blog article URLs."""
import sys
sys.path.insert(0, '.')
from services.page_type_classifier import classify_page_type

test_urls = [
    "https://brave.com/blog/place-search-improved/",
    "https://brave.com/blog/claude-cowork-amazon-bedrock-brave-mcp/",
    "https://brave.com/blog/bat-roadmap-4-0/",
    "https://brave.com/search/api/",
    "https://brave.com/category/brave-search-news/",
]
for url in test_urls:
    pt = classify_page_type(url, "")
    print(f"  {pt:20s}  {url}")
