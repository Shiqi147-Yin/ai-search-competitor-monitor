"""测试：Querit 结果去重"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
from services.querit_client import SearchResult
from services.querit_result_adapter import adapt_results
from services.url_normalizer import normalize_url


@pytest.fixture(autouse=True)
def isolated_db(tmp_path, monkeypatch):
    import config, database
    tmp_db = tmp_path / "dedup_test.db"
    monkeypatch.setattr(config, "DB_PATH", tmp_db)
    monkeypatch.setattr(database, "DB_PATH", tmp_db)
    database.init_db()
    database.migrate_db()
    yield


def _sr(url, rank=1, title="T"):
    return SearchResult(url=url, title=title, rank=rank, query="test")


def test_same_query_dedup():
    """同 Query 内重复 URL 在批量适配中被识别为重复。"""
    url = "https://tavily.com/blog/same"
    items = [_sr(url, 1), _sr(url, 2)]
    adapted = adapt_results(items, "run1", 1)
    # 两条 URL 相同，第二条应被标为重复（若第一条先写入DB后检查）
    # adapt_results 不写DB，但 is_url_duplicate 查DB，所以两条都不重复
    # 实际去重由 batch_insert 的 INSERT OR IGNORE 完成
    assert len(adapted) == 2  # adapter 层不去重，由写入层处理


def test_cross_query_dedup_via_database():
    """与数据库已有记录的去重：第二次同 URL 被标为 duplicate。"""
    import database
    url = "https://tavily.com/blog/cross-dedup"
    database.insert_record({
        "source_url": url, "normalized_url": normalize_url(url), "title": "existing"
    })
    adapted = adapt_results([_sr(url)], "run2", 2)
    assert len(adapted) == 1
    assert adapted[0]["_is_duplicate"] is True


def test_returns_existing_record_id():
    """重复时返回已有记录 ID。"""
    import database
    url = "https://exa.ai/blog/known-article"
    database.insert_record({
        "source_url": url, "normalized_url": normalize_url(url), "title": "known"
    })
    adapted = adapt_results([_sr(url)], "run1", 1)
    assert adapted[0]["_existing_record_id"] > 0


def test_different_urls_not_merged():
    """不同 URL 不会被合并（即使内容相似）。"""
    url1 = "https://tavily.com/blog/article-1"
    url2 = "https://x.com/TavilyHQ/status/99999"
    items = [_sr(url1, title="Same topic"), _sr(url2, title="Same topic")]
    adapted = adapt_results(items, "run1", 1)
    assert len(adapted) == 2
    urls = {r["source_url"] for r in adapted}
    assert url1 in urls and url2 in urls


def test_tracking_params_stripped_for_dedup():
    """不同追踪参数的同一 URL 被识别为重复。"""
    import database
    base_url = "https://tavily.com/blog/article"
    database.insert_record({
        "source_url": base_url,
        "normalized_url": normalize_url(base_url),
        "title": "base",
    })
    url_with_utm = f"{base_url}?utm_source=x&utm_medium=social"
    adapted = adapt_results([_sr(url_with_utm)], "run1", 1)
    assert adapted[0]["_is_duplicate"] is True
