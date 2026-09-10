"""测试：app 启动前 migration 已执行"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))


def test_run_migrations_called_before_page_write(tmp_path, monkeypatch):
    """init_db + run_migrations 完成后，字段必须存在才能写入。"""
    import config, database
    tmp_db = tmp_path / "startup_test.db"
    monkeypatch.setattr(config, "DB_PATH", tmp_db)
    monkeypatch.setattr(database, "DB_PATH", tmp_db)

    # 模拟 app.py 启动顺序
    database.init_db()
    database.run_migrations()

    # 字段应已存在
    cols = database.get_table_columns("querit_search_runs")
    assert "within_window_count" in cols
    assert "window_start" in cols

    # 可以安全写入
    from datetime import datetime, timezone
    now = datetime.now(timezone.utc).isoformat()
    run_id = database.create_search_run({
        "started_at": now, "status": "running", "created_at": now,
    })
    database.update_search_run(run_id, {"within_window_count": 3})
    assert database.get_search_runs()[0]["within_window_count"] == 3


def test_freshness_fields_exist_before_first_write(tmp_path, monkeypatch):
    """querit_search_results 新鲜度字段在第一次写入前已存在。"""
    import config, database
    tmp_db = tmp_path / "startup_results.db"
    monkeypatch.setattr(config, "DB_PATH", tmp_db)
    monkeypatch.setattr(database, "DB_PATH", tmp_db)

    database.init_db()
    database.run_migrations()

    cols = database.get_table_columns("querit_search_results")
    for f in ("freshness_status", "date_status", "normalized_published_at", "window_start"):
        assert f in cols, f"字段 {f} 在首次写入前不存在"
