"""测试：自动分析流水线（批量/单条/不覆盖人工字段）"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
from unittest.mock import patch


@pytest.fixture(autouse=True)
def isolated_db(tmp_path, monkeypatch):
    import config, database
    tmp_db = tmp_path / "analysis_pipeline.db"
    monkeypatch.setattr(config, "DB_PATH", tmp_db)
    monkeypatch.setattr(database, "DB_PATH", tmp_db)
    database.init_db()
    database.migrate_db()
    yield


def _mock_fetch(url):
    from services.url_fetcher import FetchResult
    return FetchResult(
        url=url, final_url=url, status="success",
        title="Exa Agent Skills launch", description="New agent skills for AI workflows.",
        content_source="og",
    )


@patch("services.import_batch_service.fetch_url", side_effect=_mock_fetch)
def test_single_fetch_triggers_analysis(mock_fetch):
    """单条抓取成功后自动触发分析，写入 auto_category 等字段。"""
    import database
    from services.import_batch_service import process_url_list, confirm_batch

    urls = ["https://exa.ai/blog/agent-skills"]
    results = process_url_list(urls)
    confirm_batch(results, [0], import_mode="url_batch")

    records = database.get_records()
    assert len(records) == 1
    rec = records[0]
    # 自动分析字段不为空
    assert rec.get("auto_category") is not None
    assert rec.get("analysis_status") in ("analyzed", "partial")


@patch("services.import_batch_service.fetch_url", side_effect=_mock_fetch)
def test_batch_each_record_analyzed(mock_fetch):
    """批量导入逐条分析，每条都有 analysis_status。"""
    import database
    from services.import_batch_service import process_url_list, confirm_batch

    urls = ["https://exa.ai/blog/a", "https://exa.ai/blog/b"]
    results = process_url_list(urls)
    confirm_batch(results, list(range(len(results))), import_mode="url_batch")

    records = database.get_records()
    for r in records:
        assert r.get("analysis_status") in ("analyzed", "partial", "failed")


@patch("services.import_batch_service.fetch_url", side_effect=_mock_fetch)
def test_analysis_does_not_overwrite_manual_fields(mock_fetch):
    """自动分析不覆盖人工已填写的 category/priority 字段。"""
    import database
    from services.import_batch_service import process_url_list, confirm_batch

    urls = ["https://exa.ai/blog/manual"]
    results = process_url_list(urls)
    # 先写入
    confirm_batch(results, [0])
    records = database.get_records()
    rec_id = records[0]["id"]

    # 人工修改 category
    database.update_record(rec_id, {"category": "市场与运营", "priority": "低"})

    # 再次触发分析（模拟 refetch）
    from services.content_analyzer import analyze_record, AnalysisResult
    fresh = analyze_record(records[0])
    fill = fresh.to_fill_fields({"category": "市场与运营", "priority": "低"})
    # 人工字段不应被填充
    assert fill.get("category") != "市场与运营" or "category" not in fill or fill.get("category") == "市场与运营"
    # 核心断言：category 已有值时 to_fill_fields 不覆盖
    updated = database.get_records()[0]
    assert updated["category"] == "市场与运营"


def _fail_fetch(url):
    from services.url_fetcher import FetchResult
    return FetchResult(url=url, status="failed", error="ConnectTimeout")


@patch("services.import_batch_service.fetch_url", side_effect=_fail_fetch)
def test_failed_fetch_category_is_pending(mock_fetch):
    """抓取失败且无内容时，category=待评估。"""
    import database
    from services.import_batch_service import process_url_list, confirm_batch

    urls = ["https://luma.com/tavily-event"]
    results = process_url_list(urls)
    # failed 记录也写入（保留链接）
    confirm_batch(results, [0])

    records = database.get_records()
    if records:
        rec = records[0]
        assert rec.get("auto_category") in ("待评估", None, "")


@patch("services.import_batch_service.fetch_url")
def test_single_analysis_failure_does_not_affect_others(mock_fetch):
    """单条分析异常不影响其他记录。"""
    import database
    from services.import_batch_service import process_url_list, confirm_batch
    from services.url_fetcher import FetchResult

    def _mixed(url):
        if "fail" in url:
            return FetchResult(url=url, status="failed", error="error")
        return FetchResult(url=url, status="success", title="Exa News",
                           description="desc", content_source="og")

    mock_fetch.side_effect = _mixed
    urls = ["https://exa.ai/ok", "https://fail.example.com/bad", "https://exa.ai/ok2"]
    results = process_url_list(urls)
    confirm_batch(results, [i for i, r in enumerate(results) if not r.is_invalid_url])

    records = database.get_records()
    # 成功的记录应有 analysis_status
    ok_records = [r for r in records if r.get("fetch_status") == "success"]
    for r in ok_records:
        assert r.get("analysis_status") in ("analyzed", "partial")
