"""test_official_monitor_pipeline.py
验证统一巡检入口的集成行为：官网和 GitHub 可独立运行、单来源失败不中断、
enable_querit_supplement=False 时不调用 Querit API。
"""
import pytest
from unittest.mock import patch, MagicMock
from services.official_source_monitor import run_official_monitor, OfficialMonitorResult
from services.website_monitor import WebsiteUpdateItem
from services.github_monitor import GitHubCommitRecord, GitHubReleaseRecord


_MOCK_CONFIG = {
    "Tavily": {
        "website": {
            "blog": ["https://www.tavily.com/blog"],
            "docs": ["https://docs.tavily.com/"],
            "sitemap": ["https://docs.tavily.com/sitemap.xml"],
        },
        "github": {
            "owner": "tavily-ai",
            "repositories": [
                {"name": "tavily-mcp", "monitor": ["commits", "releases"]},
            ],
        },
    }
}


def _blog_item():
    return WebsiteUpdateItem(
        competitor="Tavily", source_type="blog",
        source_url="https://www.tavily.com/blog/keyless",
        title="Keyless Search", published_at="2026-07-14",
        is_entry_page=False, within_window=True, import_eligible=True,
        update_status="new_page", discovery_method="official_blog_monitor",
    )


def _commit_record():
    return GitHubCommitRecord(
        repository="tavily-ai/tavily-mcp",
        commit_sha="abc1",
        commit_title="Add streaming support for Research",
        commit_url="https://github.com/tavily-ai/tavily-mcp/commit/abc1",
        commit_date="2026-07-10",
    )


@pytest.fixture
def tmp_db(tmp_path):
    import sqlite3, database
    db_file = str(tmp_path / "test_pipeline.db")
    conn = sqlite3.connect(db_file)
    conn.execute(database._CREATE_SNAPSHOTS_SQL)
    conn.commit()
    conn.close()
    return db_file


def test_pipeline_returns_official_monitor_result(tmp_db):
    with patch("services.official_source_monitor.load_monitoring_config", return_value=_MOCK_CONFIG):
        with patch("services.official_source_monitor.run_website_monitor") as mock_web:
            mock_web.return_value = {
                "blog": [_blog_item()], "docs": [], "integrations": [], "errors": []
            }
            with patch("services.official_source_monitor.run_github_monitor") as mock_gh:
                mock_gh.return_value = {
                    "commits": [_commit_record()], "releases": [], "errors": []
                }
                result = run_official_monitor(
                    "Tavily", "2026-07-08", "2026-07-17",
                    source_types=["all"], enable_querit_supplement=False,
                    db_path=tmp_db,
                )

    assert isinstance(result, OfficialMonitorResult)
    assert result.competitor == "Tavily"
    assert result.started_at != ""
    assert result.completed_at != ""


def test_website_results_contain_blog(tmp_db):
    with patch("services.official_source_monitor.load_monitoring_config", return_value=_MOCK_CONFIG):
        with patch("services.official_source_monitor.run_website_monitor") as mock_web:
            mock_web.return_value = {
                "blog": [_blog_item()], "docs": [], "integrations": [], "errors": []
            }
            with patch("services.official_source_monitor.run_github_monitor") as mock_gh:
                mock_gh.return_value = {"commits": [], "releases": [], "errors": []}
                result = run_official_monitor(
                    "Tavily", "2026-07-08", "2026-07-17",
                    source_types=["blog"], enable_querit_supplement=False,
                    db_path=tmp_db,
                )

    blog_items = [i for i in result.website_results if i.source_channel == "website_blog"]
    assert len(blog_items) >= 1


def test_github_failure_does_not_abort_website(tmp_db):
    with patch("services.official_source_monitor.load_monitoring_config", return_value=_MOCK_CONFIG):
        with patch("services.official_source_monitor.run_website_monitor") as mock_web:
            mock_web.return_value = {
                "blog": [_blog_item()], "docs": [], "integrations": [], "errors": []
            }
            with patch("services.official_source_monitor.run_github_monitor",
                       side_effect=RuntimeError("GitHub 网络失败")):
                result = run_official_monitor(
                    "Tavily", "2026-07-08", "2026-07-17",
                    source_types=["all"], enable_querit_supplement=False,
                    db_path=tmp_db,
                )

    # GitHub 失败，但 website 结果应保留
    blog_items = [i for i in result.website_results if i.source_channel == "website_blog"]
    assert len(blog_items) >= 1
    assert any("github" in str(e).lower() for e in result.errors)


def test_querit_supplement_not_called_when_disabled(tmp_db):
    with patch("services.official_source_monitor.load_monitoring_config", return_value=_MOCK_CONFIG):
        with patch("services.official_source_monitor.run_website_monitor") as mock_web:
            mock_web.return_value = {"blog": [], "docs": [], "integrations": [], "errors": []}
            with patch("services.official_source_monitor.run_github_monitor") as mock_gh:
                mock_gh.return_value = {"commits": [], "releases": [], "errors": []}
                with patch("services.official_source_monitor._run_querit_supplement") as mock_q:
                    run_official_monitor(
                        "Tavily", "2026-07-08", "2026-07-17",
                        source_types=["all"], enable_querit_supplement=False,
                        db_path=tmp_db,
                    )
                    mock_q.assert_not_called()


def test_unknown_competitor_returns_error(tmp_db):
    with patch("services.official_source_monitor.load_monitoring_config", return_value=_MOCK_CONFIG):
        result = run_official_monitor(
            "UnknownComp", "2026-07-08", "2026-07-17",
            source_types=["all"], db_path=tmp_db,
        )
    assert len(result.errors) >= 1
    assert "UnknownComp" in result.errors[0]["error"]
