"""查询数据库中三条测试 URL 的现有记录状态"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from services.url_normalizer import normalize_url
import database

URLS = [
    "https://www.tavily.com/blog/What-keyless-search-really-means-for-your-data",
    "https://luma.com/tavily-h550",
    "https://docs.tavily.com/documentation/integrations/nemo-deepagents",
]

database.init_db()
database.migrate_db()

for url in URLS:
    norm = normalize_url(url)
    print(f"\nURL: {url}")
    print(f"normalized: {norm}")

    with database._get_conn() as conn:
        row = conn.execute(
            "SELECT id, competitor, source_platform, title, fetch_status, review_status, "
            "imported_batch_id, collected_at, updated_at, normalized_url, source_url "
            "FROM competitor_updates WHERE normalized_url = ? OR source_url = ? LIMIT 1",
            (norm, norm)
        ).fetchone()

    if row:
        r = dict(row)
        print(f"  record_id:         {r['id']}")
        print(f"  competitor:        {r['competitor']}")
        print(f"  source_platform:   {r['source_platform']}")
        print(f"  title:             {r['title']}")
        print(f"  fetch_status:      {r['fetch_status']}")
        print(f"  review_status:     {r['review_status']}")
        print(f"  imported_batch_id: {r['imported_batch_id']}")
        print(f"  collected_at:      {r['collected_at']}")
        print(f"  updated_at:        {r['updated_at']}")
    else:
        print("  [NOT IN DATABASE]")
