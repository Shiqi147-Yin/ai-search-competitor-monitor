"""测试：Querit 导入确认（未确认不写正式库）"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
from services.querit_client import SearchResult
from services.querit_result_adapter import adapt_results
from services.data_service import batch_insert, get_current_week_id


@pytest.fixture(autouse=True)
def isolated_db(tmp_path, monkeypatch):
    import config, database
    tmp_db = tmp_path / "import_confirm_test.db"
    monkeypatch.setattr(config, "DB_PATH", tmp_db)
    monkeypatch.setattr(database, "DB_PATH", tmp_db)
    database.init_db()
    database.migrate_db()
    yield


def _sr(url, title="T"):
    return SearchResult(url=url, title=title, rank=1, query="test",
                        raw_source="", raw_metadata={})


def test_unconfirmed_results_not_in_production_db():
    """未确认的结果不写入正式竞品记录表。"""
    import database
    items = [_sr("https://tavily.com/unconfirmed")]
    adapt_results(items, "run1", 1)
    # adapt_results 不写 competitor_updates
    records = database.get_records()
    assert len(records) == 0


def test_confirmed_results_go_to_pending_review():
    """确认导入后 review_status=待审核。"""
    import database
    items = [_sr("https://tavily.com/confirmed")]
    adapted = adapt_results(items, "run1", 1)
    clean = [{k: v for k, v in r.items() if not k.startswith("_") and k != "_analysis"}
             for r in adapted]
    batch_insert(clean)
    records = database.get_records({"review_status": "待审核"})
    assert len(records) == 1


def test_confirmed_does_not_go_to_weekly_dashboard():
    """确认导入后不进入本周主页（review_status=待审核，非已确认）。"""
    import database
    from services.data_service import get_weekly_dashboard
    items = [_sr("https://exa.ai/dashboard-test")]
    adapted = adapt_results(items, "run1", 1)
    clean = [{k: v for k, v in r.items() if not k.startswith("_") and k != "_analysis"}
             for r in adapted]
    batch_insert(clean)
    dashboard = get_weekly_dashboard()
    assert all(r["review_status"] == "已确认" for r in dashboard)
    assert len(dashboard) == 0  # 没有已确认记录


def test_duplicate_not_inserted():
    """重复记录不新增。"""
    import database
    url = "https://tavily.com/dup-confirm"
    database.insert_record({"source_url": url, "normalized_url": url, "title": "existing"})
    items = [_sr(url)]
    adapted = adapt_results(items, "run1", 1)
    clean = [{k: v for k, v in r.items() if not k.startswith("_") and k != "_analysis"}
             for r in adapted if not r.get("_is_duplicate")]
    count_before = len(database.get_records())
    batch_insert(clean)
    assert len(database.get_records()) == count_before


def test_source_mode_is_querit_api():
    """导入后 source_mode=querit_api。"""
    import database
    items = [_sr("https://brave.com/source-mode-test")]
    adapted = adapt_results(items, "run1", 1)
    clean = [{k: v for k, v in r.items() if not k.startswith("_") and k != "_analysis"}
             for r in adapted]
    batch_insert(clean)
    records = database.get_records()
    assert records[0]["source_mode"] == "querit_api"
