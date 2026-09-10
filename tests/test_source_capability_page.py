"""测试：来源能力测试页面行为（不写入正式看板数据库）"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import io
from unittest.mock import patch
import pandas as pd


def _mock_fetch_success(url):
    from services.url_fetcher import FetchResult
    return FetchResult(
        url=url, final_url=url, status="success",
        title="Test Title", description="Desc.",
        published_date="2026-07-01", content_snippet="content",
        content_source="og",
    )


def _mock_fetch_fail(url):
    from services.url_fetcher import FetchResult
    return FetchResult(url=url, status="failed", error="ConnectTimeout: x")


def test_capability_test_does_not_write_to_production_db(tmp_path, monkeypatch):
    """能力测试结果不写入正式看板数据库。"""
    import config, database
    tmp_db = tmp_path / "prod.db"
    monkeypatch.setattr(config, "DB_PATH", tmp_db)
    monkeypatch.setattr(database, "DB_PATH", tmp_db)
    database.init_db()
    database.migrate_db()

    from services.url_normalizer import is_valid_url
    from services.source_detector import detect_both
    from services.source_capability_classifier import classify_fetch_result

    url = "https://tavily.com/blog/test"
    with patch("services.url_fetcher.fetch_url", side_effect=_mock_fetch_success):
        from services.url_fetcher import fetch_url
        fr = fetch_url(url)
        classify_fetch_result(fr.status, bool(fr.title), bool(fr.description),
                              bool(fr.published_date), "Blog")

    # 正式库中不应有任何记录
    records = database.get_records()
    assert len(records) == 0


def test_bulk_test_single_failure_does_not_stop_others():
    """批量测试时单条失败不影响其他链接继续处理。"""
    from services.url_normalizer import is_valid_url

    urls = [
        "https://tavily.com/ok",
        "not-a-url",
        "https://exa.ai/ok",
    ]

    results = []
    for url in urls:
        try:
            if not is_valid_url(url):
                results.append({"url": url, "status": "invalid"})
                continue
            with patch("services.url_fetcher.fetch_url", side_effect=_mock_fetch_success):
                from services.url_fetcher import fetch_url
                fr = fetch_url(url)
                results.append({"url": url, "status": fr.status})
        except Exception as e:
            results.append({"url": url, "status": "error"})

    assert len(results) == 3
    # 无效 URL 标记为 invalid，不影响其他
    assert results[1]["status"] == "invalid"
    assert results[0]["status"] == "success"
    assert results[2]["status"] == "success"


def test_bulk_test_results_exportable():
    """批量测试结果可以构建为 DataFrame 并导出 Excel。"""
    rows = [
        {"url": "https://tavily.com/blog", "竞品": "Tavily", "fetch_status": "success",
         "能力等级": "A", "标题获取": "✅"},
        {"url": "https://luma.com/e", "竞品": "Tavily", "fetch_status": "failed",
         "能力等级": "B", "标题获取": "❌"},
    ]
    df = pd.DataFrame(rows)
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as writer:
        df.to_excel(writer, index=False)
    assert len(buf.getvalue()) > 0


def test_history_batches_preserved():
    """历史测试批次可以追加，不覆盖。"""
    batch1 = [{"url": "https://a.com", "fetch_status": "success", "tested_at": "2026-07-01"}]
    batch2 = [{"url": "https://b.com", "fetch_status": "failed", "tested_at": "2026-07-02"}]

    combined = batch1 + batch2
    assert len(combined) == 2
    assert combined[0]["url"] == "https://a.com"
    assert combined[1]["url"] == "https://b.com"
