"""测试：Querit 结果适配器"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
from services.querit_client import SearchResult
from services.querit_result_adapter import adapt_result, adapt_results


@pytest.fixture(autouse=True)
def isolated_db(tmp_path, monkeypatch):
    import config, database
    tmp_db = tmp_path / "adapter_test.db"
    monkeypatch.setattr(config, "DB_PATH", tmp_db)
    monkeypatch.setattr(database, "DB_PATH", tmp_db)
    database.init_db()
    database.migrate_db()
    yield


def _result(**kwargs):
    base = dict(
        title="Tavily streaming API released",
        url="https://docs.tavily.com/changelog/streaming",
        content="New streaming search API for agents.",
        summary="Tavily releases streaming API.",
        published_date="2026-07-15",
        score=0.95, rank=1, query="Tavily updates",
        raw_source="https://docs.tavily.com", raw_metadata={},
    )
    base.update(kwargs)
    return SearchResult(**base)


def test_adapt_result_maps_url_and_title():
    """URL 和标题正确映射。"""
    r = _result()
    rec = adapt_result(r, "run1", 1)
    assert rec is not None
    assert rec["source_url"] == r.url
    assert rec["title"] == r.title


def test_adapt_result_source_mode_is_querit_api():
    """source_mode 固定为 querit_api。"""
    rec = adapt_result(_result(), "run1", 1)
    assert rec["source_mode"] == "querit_api"


def test_adapt_result_detects_competitor_from_url():
    """竞品从 URL 域名识别，不强制使用 Query 竞品。"""
    r = _result(url="https://exa.ai/blog/news", query="Tavily updates")
    rec = adapt_result(r, "run1", 1, query_competitor="Tavily")
    # exa.ai 应识别为 Exa，不被 Tavily 覆盖
    assert rec["competitor"] == "Exa"


def test_adapt_result_fallback_to_query_competitor():
    """URL 无法识别竞品时，使用 Query 竞品作为兜底。"""
    r = _result(url="https://unknown-domain.com/news", query="Tavily updates")
    rec = adapt_result(r, "run1", 1, query_competitor="Tavily")
    assert rec["competitor"] == "Tavily"


def test_missing_url_returns_none():
    """缺 URL 的结果返回 None。"""
    r = _result(url="")
    rec = adapt_result(r, "run1", 1)
    assert rec is None


def test_adapt_results_skips_invalid():
    """批量适配时跳过无效结果，单条异常不中断。"""
    items = [_result(), _result(url=""), _result(url="https://brave.com/search")]
    adapted = adapt_results(items, "run1", 1)
    assert len(adapted) == 2


def test_duplicate_flag_set_when_url_in_db():
    """URL 已在数据库中时，_is_duplicate=True 且返回 existing_record_id。"""
    import database
    from services.url_normalizer import normalize_url
    url = "https://docs.tavily.com/already-exists"
    database.insert_record({
        "source_url": url, "normalized_url": normalize_url(url),
        "title": "existing",
    })
    r = _result(url=url)
    rec = adapt_result(r, "run1", 1)
    assert rec["_is_duplicate"] is True
    assert rec["_existing_record_id"] > 0
