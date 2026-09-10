"""数据库 Schema 检查脚本"""
import sys
import io
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

from env_loader import load_env
load_env()
import database

database.init_db()
database.run_migrations()

for tbl in ("querit_search_runs", "querit_search_results", "competitor_updates", "import_batches"):
    cols = sorted(database.get_table_columns(tbl))
    print(f"\n{tbl} ({len(cols)} 列):")
    for c in cols:
        print(f"  {c}")
