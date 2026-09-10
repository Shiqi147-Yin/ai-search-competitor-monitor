"""安全清理脚本：删除指定三个 URL 的测试记录（不自动执行，需手动确认）。
用法：python scripts/cleanup_test_records.py
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import database
from services.url_normalizer import normalize_url

TEST_URLS = [
    "https://www.tavily.com/blog/What-keyless-search-really-means-for-your-data",
    "https://luma.com/tavily-h550",
    "https://docs.tavily.com/documentation/integrations/nemo-deepagents",
]

database.init_db()
database.migrate_db()

print("以下记录将被删除（仅限这三条 URL）：\n")
ids_to_delete = []

for url in TEST_URLS:
    norm = normalize_url(url)
    existing = database.get_record_by_url(norm)
    if existing:
        print(f"  ID={existing['id']}  competitor={existing['competitor']}  "
              f"fetch_status={existing['fetch_status']}  url={url[:60]}")
        ids_to_delete.append(existing['id'])
    else:
        print(f"  [不在数据库中] {url[:60]}")

if not ids_to_delete:
    print("\n没有找到需要删除的记录。")
    sys.exit(0)

print(f"\n即将删除 {len(ids_to_delete)} 条记录，ID: {ids_to_delete}")
confirm = input("确认删除？输入 yes 继续，其他任意键取消：").strip().lower()

if confirm == "yes":
    with database._get_conn() as conn:
        for rid in ids_to_delete:
            conn.execute("DELETE FROM competitor_updates WHERE id = ?", (rid,))
        conn.commit()
    print(f"已删除 {len(ids_to_delete)} 条记录。")
else:
    print("已取消，未删除任何记录。")
