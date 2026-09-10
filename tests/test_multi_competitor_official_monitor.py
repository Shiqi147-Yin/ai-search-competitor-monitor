"""test_multi_competitor_official_monitor.py
验证多竞品支持：Tavily 和 Exa 配置互不干扰，各自加载正确配置。
"""
import pytest
from unittest.mock import patch, MagicMock
from services.official_source_monitor import load_monitoring_config, run_official_monitor


def test_config_contains_both_tavily_and_exa():
    config = load_monitoring_config()
    assert "Tavily" in config, "Tavily 配置缺失"
    assert "Exa" in config, "Exa 配置缺失"


def test_tavily_config_has_blog_and_github(tmp_path):
    config = load_monitoring_config()
    tavily = config["Tavily"]
    assert "blog" in tavily.get("website", {})
    assert "github" in tavily
    assert tavily["github"]["owner"] == "tavily-ai"


def test_exa_config_has_blog_and_github():
    config = load_monitoring_config()
    exa = config["Exa"]
    assert "blog" in exa.get("website", {})
    assert "github" in exa
    assert exa["github"]["owner"] == "exa-labs"


def test_exa_github_repos_include_exa_mcp_server():
    config = load_monitoring_config()
    repos = config["Exa"]["github"].get("repositories", [])
    names = [r.get("name", "") if isinstance(r, dict) else r for r in repos]
    assert "exa-mcp-server" in names


def test_competitors_do_not_share_data():
    """Tavily 和 Exa 结果不互相污染。"""
    mock_tavily = MagicMock()
    mock_tavily.website_results = []
    mock_tavily.github_results = []
    mock_tavily.querit_supplement_results = []
    mock_tavily.errors = []
    mock_tavily.source_stats = {}
    mock_tavily.completed_at = "2026-08-10T00:00:00Z"

    mock_exa = MagicMock()
    mock_exa.website_results = []
    mock_exa.github_results = []
    mock_exa.querit_supplement_results = []
    mock_exa.errors = []
    mock_exa.source_stats = {}
    mock_exa.completed_at = "2026-08-10T00:01:00Z"

    with patch("services.official_source_monitor.run_website_monitor") as mock_web:
        mock_web.return_value = {"blog": [], "docs": [], "integrations": [], "errors": []}
        with patch("services.official_source_monitor.run_github_monitor") as mock_gh:
            mock_gh.return_value = {"commits": [], "releases": [], "errors": []}

            result_tavily = run_official_monitor("Tavily", "2026-07-08", "2026-07-17", ["all"])
            result_exa = run_official_monitor("Exa", "2026-07-27", "2026-08-10", ["all"])

    assert result_tavily.competitor == "Tavily"
    assert result_exa.competitor == "Exa"
    assert result_tavily.window_start != result_exa.window_start
