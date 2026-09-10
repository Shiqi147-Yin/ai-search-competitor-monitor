"""测试：业务数据服务"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
from services.data_service import (
    get_current_week_id,
    get_weekly_dashboard,
    batch_insert,
    get_pending_review,
    get_history,
    confirm_record,
    ignore_record,
)


@pytest.fixture(autouse=True)
def isolated_db(tmp_path, monkeypatch):
    """每个测试使用独立临时数据库。"""
    import config, database
    tmp_db = tmp_path / "svc_test.db"
    monkeypatch.setattr(config, "DB_PATH", tmp_db)
    monkeypatch.setattr(database, "DB_PATH", tmp_db)
    database.init_db()
    yield


def _insert_confirmed(week_id: str, competitor: str = "Tavily",
                      category: str = "产品与功能", url_suffix: str = "1"):
    """插入一条已确认记录的辅助函数。"""
    import database
    database.insert_record({
        "title": f"测试_{url_suffix}",
        "source_url": f"https://example.com/{url_suffix}",
        "competitor": competitor,
        "category": category,
        "week_id": week_id,
        "review_status": "已确认",
        "priority": "高",
    })


def test_get_weekly_dashboard_returns_current_week_only():
    """按当前周查询只返回当前周数据。"""
    current_week = get_current_week_id()
    _insert_confirmed(current_week, url_suffix="w1")
    _insert_confirmed("2025-W01", url_suffix="old1")  # 旧数据

    results = get_weekly_dashboard(current_week)
    assert all(r["week_id"] == current_week for r in results), "应只返回当前周数据"
    assert len(results) >= 1


def test_filter_by_competitor():
    """按竞品筛选应只返回对应竞品。"""
    current_week = get_current_week_id()
    _insert_confirmed(current_week, competitor="Tavily", url_suffix="c1")
    _insert_confirmed(current_week, competitor="Exa", url_suffix="c2")

    results = get_weekly_dashboard(current_week, extra_filters={"competitor": ["Tavily"]})
    assert all(r["competitor"] == "Tavily" for r in results)
    assert len(results) == 1


def test_ignored_not_in_dashboard():
    """已忽略的数据不应出现在本周看板中。"""
    import database
    current_week = get_current_week_id()
    database.insert_record({
        "title": "忽略测试",
        "source_url": "https://example.com/ignored",
        "week_id": current_week,
        "review_status": "已忽略",
        "competitor": "Brave",
    })
    results = get_weekly_dashboard(current_week)
    assert all(r["review_status"] == "已确认" for r in results)


def test_history_returns_all_confirmed():
    """历史查询应返回所有已确认记录（跨周）。"""
    _insert_confirmed("2026-W01", url_suffix="h1")
    _insert_confirmed("2026-W10", url_suffix="h2")
    _insert_confirmed("2026-W20", url_suffix="h3")

    history = get_history()
    assert len(history) >= 3
    assert all(r["review_status"] == "已确认" for r in history)
