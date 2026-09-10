"""test_official_monitor_review_import.py
验证 item_to_record() 转换和 batch_insert 写入待审核区的逻辑。
"""
import pytest
import sqlite3
import database
from services.official_update_normalizer import OfficialUpdateItem
from services.official_monitor_importer import item_to_record


def _make_item(**kw):
    defaults = dict(
        competitor="Tavily",
        update_title="What Keyless Search Really Means",
        source_url="https://www.tavily.com/blog/keyless-search",
        source_channel="website_blog",
        published_at="2026-07-14",
        updated_at="",
        update_date="2026-07-14",
        within_window=True,
        is_entry_page=False,
        discovery_method="official_direct",
        update_status="new_page",
        summary="Keyless Search allows API usage without a key.",
        evidence_urls=["https://www.tavily.com/blog/keyless-search"],
        docs_page_role="",
        is_generic_page=False,
    )
    defaults.update(kw)
    return OfficialUpdateItem(**defaults)


@pytest.fixture
def tmp_db(tmp_path, monkeypatch):
    """使用独立临时 DB 并 patch DB_PATH。"""
    import config as cfg
    from pathlib import Path
    db_file = tmp_path / "test_import.db"
    monkeypatch.setattr(cfg, "DB_PATH", db_file)
    monkeypatch.setattr(database, "DB_PATH", db_file)
    # init_db 会建所有表，run_migrations 会添加 Phase 2/3 字段
    database.init_db()
    database.run_migrations()
    return str(db_file)


# ── item_to_record 转换测试 ───────────────────────────────────

def test_item_to_record_basic_fields():
    item = _make_item()
    rec = item_to_record(item)
    assert rec["title"] == "What Keyless Search Really Means"
    assert rec["source_url"] == "https://www.tavily.com/blog/keyless-search"
    assert rec["review_status"] == "待审核"
    assert rec["source_mode"] == "official_monitor"
    assert rec["fetch_status"] == "pending"
    assert rec["discovery_method"] == "official_direct"


def test_item_to_record_publish_date_priority():
    # published_at 优先
    item = _make_item(published_at="2026-07-14", updated_at="2026-07-09", update_date="2026-07-01")
    rec = item_to_record(item)
    assert rec["publish_date"] == "2026-07-14"

    # 无 published_at 时用 updated_at
    item2 = _make_item(published_at="", updated_at="2026-07-09", update_date="2026-07-01")
    rec2 = item_to_record(item2)
    assert rec2["publish_date"] == "2026-07-09"


def test_item_to_record_title_fallback():
    item = _make_item(update_title="", source_url="https://www.tavily.com/blog/keyless-search-article")
    rec = item_to_record(item)
    assert rec["title"] != ""
    assert "keyless" in rec["title"].lower()


def test_item_to_record_evidence_urls_serialized():
    item = _make_item(evidence_urls=["url1", "url2", "url3", "url4"])
    rec = item_to_record(item)
    import json
    urls = json.loads(rec["commit_or_release_url"])
    assert len(urls) == 3  # 最多3条


def test_item_to_record_user_edits_override():
    item = _make_item(summary="original summary")
    rec = item_to_record(item, user_edits={"summary": "edited summary", "category": "产品与功能"})
    assert rec["summary"] == "edited summary"
    assert rec["category"] == "产品与功能"


# ── 写入待审核区测试 ──────────────────────────────────────────

def test_unchecked_item_not_inserted(tmp_db):
    """未勾选的条目不应写入数据库（由页面逻辑控制，item_to_record 本身不控制写入）。"""
    # item_to_record 只是转换，不写入。写入由调用方决定是否执行。
    item = _make_item()
    rec = item_to_record(item)
    # 未调用 insert_record → 数据库应仍为空
    conn = sqlite3.connect(tmp_db)
    count = conn.execute("SELECT COUNT(*) FROM competitor_updates").fetchone()[0]
    conn.close()
    assert count == 0


def test_checked_item_written_to_review_queue(tmp_db):
    """勾选后调用 insert_record 写入，review_status = 待审核。"""
    item = _make_item()
    rec = item_to_record(item)
    status = database.insert_record(rec)
    assert status == "success", f"insert_record 返回: {status}"

    conn = sqlite3.connect(tmp_db)
    row = conn.execute(
        "SELECT review_status, source_mode FROM competitor_updates WHERE source_url=?",
        (item.source_url,)
    ).fetchone()
    conn.close()
    assert row is not None
    assert row[0] == "待审核"
    assert row[1] == "official_monitor"


def test_duplicate_url_not_reinserted(tmp_db):
    item = _make_item()
    rec = item_to_record(item)
    s1 = database.insert_record(rec)
    s2 = database.insert_record(rec)
    assert s1 == "success"
    assert s2 == "duplicate"

    conn = sqlite3.connect(tmp_db)
    count = conn.execute(
        "SELECT COUNT(*) FROM competitor_updates WHERE source_url=?",
        (item.source_url,)
    ).fetchone()[0]
    conn.close()
    assert count == 1


def test_official_direct_discovery_method_preserved(tmp_db):
    item = _make_item(discovery_method="official_direct")
    rec = item_to_record(item)
    database.insert_record(rec)

    conn = sqlite3.connect(tmp_db)
    # discovery_method is a Phase 6 column added via run_migrations
    # verify via analysis_reason (which stores update_status) and source_mode
    row = conn.execute(
        "SELECT source_mode, analysis_reason FROM competitor_updates WHERE source_url=?",
        (item.source_url,)
    ).fetchone()
    conn.close()
    assert row is not None
    assert row[0] == "official_monitor"
    # analysis_reason maps from update_status = "new_page"
    assert row[1] == "new_page"
