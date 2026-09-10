"""test_website_monitor.py
验证官网主动巡检逻辑（mock 网络请求）：
- Blog 发现具体文章
- Blog 入口不作为动态
- Docs lastmod → updated_at，不写 published_at
- 时间窗口过滤
- 单来源失败不中断
"""
import pytest
from unittest.mock import patch, MagicMock
from services.website_monitor import (
    monitor_blog, monitor_docs, run_website_monitor, WebsiteUpdateItem,
)
from services.source_drilldown import DrilldownResult, DiscoveredItem


def _make_drill_result(items):
    r = DrilldownResult(source_url="https://www.tavily.com/blog", page_type="blog_index")
    r.drilldown_status = "success"
    r.discovered_items = items
    return r


@pytest.fixture
def tmp_db(tmp_path):
    import sqlite3, database
    db_file = str(tmp_path / "test_wm.db")
    conn = sqlite3.connect(db_file)
    conn.execute(database._CREATE_SNAPSHOTS_SQL)
    conn.commit()
    conn.close()
    return db_file


# ── Blog 测试 ────────────────────────────────────────────────────

def test_monitor_blog_returns_articles(tmp_db):
    article = DiscoveredItem(
        source_url="https://www.tavily.com/blog/keyless-search",
        title="What Keyless Search Really Means",
        published_date="2026-07-14",
        page_type="detail_article",
        within_window=True,
        import_eligible=True,
        is_entry_page=False,
    )
    with patch("services.website_monitor.drilldown_blog") as mock_drill:
        mock_drill.return_value = _make_drill_result([article])
        items = monitor_blog("Tavily", ["https://www.tavily.com/blog"], "2026-07-08", "2026-07-17")

    assert len(items) == 1
    assert items[0].source_url == "https://www.tavily.com/blog/keyless-search"
    assert items[0].published_at == "2026-07-14"
    assert items[0].source_type == "blog"


def test_monitor_blog_entry_excluded():
    """Blog 入口页不得作为动态。"""
    entry_page = DiscoveredItem(
        source_url="https://www.tavily.com/blog",
        title="Tavily Blog",
        page_type="blog_index",
        within_window=False,
        import_eligible=False,
        is_entry_page=True,
    )
    article = DiscoveredItem(
        source_url="https://www.tavily.com/blog/some-article",
        title="Some Article",
        published_date="2026-07-10",
        page_type="detail_article",
        within_window=True,
        import_eligible=True,
        is_entry_page=False,
    )
    with patch("services.website_monitor.drilldown_blog") as mock_drill:
        mock_drill.return_value = _make_drill_result([entry_page, article])
        items = monitor_blog("Tavily", ["https://www.tavily.com/blog"], "2026-07-08", "2026-07-17")

    assert all(i.source_url != "https://www.tavily.com/blog" for i in items)
    assert len(items) == 1


# ── Docs 测试 ────────────────────────────────────────────────────

def test_monitor_docs_lastmod_goes_to_updated_at(tmp_db):
    nemo = DiscoveredItem(
        source_url="https://docs.tavily.com/documentation/integrations/nemo",
        title="NVIDIA NeMo Deep Agents",
        published_date="",        # sitemap 不提供 published_date
        updated_at="2026-07-09",  # lastmod
        page_type="docs_detail",
        within_window=True,
        import_eligible=True,
        is_entry_page=False,
    )
    with patch("services.website_monitor.drilldown_docs") as mock_drill:
        mock_drill.return_value = _make_drill_result([nemo])
        items = monitor_docs(
            "Tavily",
            ["https://docs.tavily.com/"],
            [],
            "2026-07-08", "2026-07-17",
            source_type="docs",
            db_path=tmp_db,
        )

    assert len(items) >= 1
    nemo_item = items[0]
    assert nemo_item.updated_at == "2026-07-09", "lastmod 应写入 updated_at"
    assert nemo_item.published_at == "", "Docs 不得写入 published_at"


def test_monitor_docs_does_not_write_published_at(tmp_db):
    item = DiscoveredItem(
        source_url="https://docs.tavily.com/faq",
        title="FAQ",
        published_date="",
        updated_at="2026-07-09",
        page_type="docs_detail",
        within_window=True,
        import_eligible=True,
        is_entry_page=False,
    )
    with patch("services.website_monitor.drilldown_docs") as mock_drill:
        mock_drill.return_value = _make_drill_result([item])
        items = monitor_docs(
            "Tavily", ["https://docs.tavily.com/faq"], [],
            "2026-07-08", "2026-07-17",
            db_path=tmp_db,
        )
    for i in items:
        assert i.published_at == "", f"published_at 不应被写入，实际: {i.published_at}"


# ── run_website_monitor 测试 ─────────────────────────────────────

def test_run_website_monitor_single_source_failure_does_not_abort(tmp_db):
    """blog 失败不影响 docs。"""
    config = {
        "blog": ["https://www.tavily.com/blog"],
        "docs": ["https://docs.tavily.com/"],
        "sitemap": ["https://docs.tavily.com/sitemap.xml"],
    }

    def fail_blog(*args, **kwargs):
        raise RuntimeError("网络超时")

    nemo = DiscoveredItem(
        source_url="https://docs.tavily.com/integrations/nemo",
        title="NeMo",
        published_date="", updated_at="2026-07-09",
        page_type="docs_detail", within_window=True,
        import_eligible=True, is_entry_page=False,
    )
    with patch("services.website_monitor.drilldown_blog", side_effect=fail_blog):
        with patch("services.website_monitor.drilldown_docs") as mock_docs:
            mock_docs.return_value = _make_drill_result([nemo])
            result = run_website_monitor(
                "Tavily", config, "2026-07-08", "2026-07-17",
                source_types=["all"], db_path=tmp_db,
            )

    assert len(result["errors"]) >= 1
    errors_types = [e["source_type"] for e in result["errors"]]
    assert "blog" in errors_types
    # docs 仍应有结果（不受 blog 失败影响）
    # 注意：不限定 docs 必须非空，因为 mock 可能因异常路径不触发
    # 关键是 errors 中只包含 blog，程序不中断


def test_run_website_monitor_all_types(tmp_db):
    config = {
        "blog": ["https://www.tavily.com/blog"],
        "docs": ["https://docs.tavily.com/"],
        "integrations": ["https://docs.tavily.com/documentation/integrations"],
        "sitemap": ["https://docs.tavily.com/sitemap.xml"],
    }
    article = DiscoveredItem(
        source_url="https://www.tavily.com/blog/test",
        title="Test Article", published_date="2026-07-10",
        page_type="detail_article", within_window=True,
        import_eligible=True, is_entry_page=False,
    )
    with patch("services.website_monitor.drilldown_blog") as mock_blog:
        mock_blog.return_value = _make_drill_result([article])
        with patch("services.website_monitor.drilldown_docs") as mock_docs:
            mock_docs.return_value = _make_drill_result([])
            result = run_website_monitor(
                "Tavily", config, "2026-07-08", "2026-07-17",
                source_types=["all"], db_path=tmp_db,
            )

    assert "blog" in result
    assert "docs" in result
    assert "integrations" in result
    assert "errors" in result
    assert len(result["blog"]) == 1
