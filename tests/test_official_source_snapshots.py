"""test_official_source_snapshots.py
验证 official_source_snapshots 表的 CRUD、首次发现、再次检查、内容变化等场景。
"""
import os
import tempfile
import pytest

import database
from services.docs_snapshot_store import (
    upsert_snapshot, get_snapshot, list_snapshots, mark_inactive,
)


@pytest.fixture
def tmp_db(tmp_path):
    """每个测试用独立临时 DB。"""
    db_file = str(tmp_path / "test_snapshots.db")
    # 用 sqlite3 直接建表
    import sqlite3
    conn = sqlite3.connect(db_file)
    conn.execute(database._CREATE_SNAPSHOTS_SQL)
    conn.commit()
    conn.close()
    return db_file


def test_first_insert_creates_snapshot(tmp_db):
    result = upsert_snapshot(
        competitor="Tavily",
        source_url="https://docs.tavily.com/integrations/nemo",
        source_type="docs",
        page_role="integration",
        title="NVIDIA NeMo",
        content_hash="abc123",
        normalized_content="NeMo integration content",
        update_status="new_page",
        db_path=tmp_db,
    )
    assert result["action"] == "inserted"
    assert result["previous_hash"] == ""

    snap = get_snapshot("Tavily", "https://docs.tavily.com/integrations/nemo", db_path=tmp_db)
    assert snap is not None
    assert snap["page_role"] == "integration"
    assert snap["content_hash"] == "abc123"
    assert snap["first_seen_at"] != ""
    assert snap["is_active"] == 1


def test_second_check_updates_last_seen(tmp_db):
    upsert_snapshot(
        competitor="Tavily",
        source_url="https://docs.tavily.com/faq",
        source_type="docs",
        page_role="faq",
        title="FAQ",
        content_hash="hash1",
        normalized_content="Q1: ...",
        update_status="first_seen",
        db_path=tmp_db,
    )
    snap1 = get_snapshot("Tavily", "https://docs.tavily.com/faq", db_path=tmp_db)

    import time; time.sleep(0.01)
    result2 = upsert_snapshot(
        competitor="Tavily",
        source_url="https://docs.tavily.com/faq",
        source_type="docs",
        page_role="faq",
        title="FAQ",
        content_hash="hash1",
        normalized_content="Q1: ...",
        update_status="unchanged",
        db_path=tmp_db,
    )
    assert result2["action"] == "updated"
    snap2 = get_snapshot("Tavily", "https://docs.tavily.com/faq", db_path=tmp_db)
    assert snap2["update_status"] == "unchanged"
    # first_seen_at 不变
    assert snap2["first_seen_at"] == snap1["first_seen_at"]


def test_content_change_updates_hash(tmp_db):
    upsert_snapshot(
        competitor="Tavily", source_url="https://docs.tavily.com/changelog",
        source_type="docs", page_role="changelog", title="Changelog",
        content_hash="old_hash", normalized_content="v1 content",
        update_status="first_seen", db_path=tmp_db,
    )
    upsert_snapshot(
        competitor="Tavily", source_url="https://docs.tavily.com/changelog",
        source_type="docs", page_role="changelog", title="Changelog",
        content_hash="new_hash", normalized_content="v1 content + v2 new feature",
        update_status="substantive_update", db_path=tmp_db,
    )
    snap = get_snapshot("Tavily", "https://docs.tavily.com/changelog", db_path=tmp_db)
    assert snap["content_hash"] == "new_hash"
    assert snap["update_status"] == "substantive_update"


def test_unchanged_content_keeps_status(tmp_db):
    upsert_snapshot(
        competitor="Tavily", source_url="https://docs.tavily.com/welcome",
        source_type="docs", page_role="welcome", title="Welcome",
        content_hash="same_hash", normalized_content="Welcome to Tavily.",
        update_status="unchanged", db_path=tmp_db,
    )
    snap = get_snapshot("Tavily", "https://docs.tavily.com/welcome", db_path=tmp_db)
    assert snap["update_status"] == "unchanged"


def test_mark_inactive(tmp_db):
    upsert_snapshot(
        competitor="Tavily", source_url="https://docs.tavily.com/old-page",
        source_type="docs", page_role="generic", title="Old Page",
        content_hash="h1", normalized_content="...",
        update_status="first_seen", db_path=tmp_db,
    )
    mark_inactive("Tavily", "https://docs.tavily.com/old-page", db_path=tmp_db)
    snap = get_snapshot("Tavily", "https://docs.tavily.com/old-page", db_path=tmp_db)
    assert snap["is_active"] == 0


def test_list_snapshots_filter(tmp_db):
    for url, role, status in [
        ("https://docs.tavily.com/a", "integration", "new_page"),
        ("https://docs.tavily.com/b", "faq", "unchanged"),
        ("https://docs.tavily.com/c", "integration", "substantive_update"),
    ]:
        upsert_snapshot(
            competitor="Tavily", source_url=url, source_type="docs",
            page_role=role, title="T", content_hash="h", normalized_content="",
            update_status=status, db_path=tmp_db,
        )
    snaps = list_snapshots("Tavily", source_type="docs", db_path=tmp_db)
    assert len(snaps) == 3

    integrations = [s for s in snaps if s["page_role"] == "integration"]
    assert len(integrations) == 2
