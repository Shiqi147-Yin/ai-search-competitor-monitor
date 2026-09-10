"""test_run_official_monitor_cli.py
验证 CLI 过滤行为：默认不打印窗口外结果；--show-outside-window 可显示。
"""
import sys
import os
import pytest
from unittest.mock import patch, MagicMock

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _ROOT)

from services.official_update_normalizer import OfficialUpdateItem


def _make_result(blog_in_window=1, blog_outside=2, github_events=1):
    """构建 mock OfficialMonitorResult。"""
    website = []
    for i in range(blog_in_window):
        website.append(OfficialUpdateItem(
            competitor="Tavily",
            update_title=f"Keyless Search Blog {i}",
            source_channel="website_blog",
            source_url=f"https://www.tavily.com/blog/keyless-{i}",
            published_at="2026-07-14",
            within_window=True,
            is_entry_page=False,
            is_generic_page=False,
        ))
    for i in range(blog_outside):
        website.append(OfficialUpdateItem(
            competitor="Tavily",
            update_title=f"Old Blog {i}",
            source_channel="website_blog",
            source_url=f"https://www.tavily.com/blog/old-{i}",
            published_at="2026-05-01",
            within_window=False,
            is_entry_page=False,
            is_generic_page=False,
        ))

    github = []
    for i in range(github_events):
        github.append(OfficialUpdateItem(
            competitor="Tavily",
            update_title="tavily-mcp: research streaming timeout",
            source_channel="github_commit_group",
            source_url=f"https://github.com/tavily-ai/tavily-mcp/commit/abc{i}",
            update_date="2026-07-10",
            within_window=True,
            evidence_urls=[f"https://github.com/tavily-ai/tavily-mcp/commit/abc{i}"],
        ))

    mock_result = MagicMock()
    mock_result.website_results = website
    mock_result.github_results = github
    mock_result.querit_supplement_results = []
    mock_result.errors = []
    mock_result.source_stats = {}
    mock_result.completed_at = "2026-08-10T03:00:00Z"
    return mock_result


def _run_cli(args_list, mock_result):
    """运行 CLI main() 并捕获 stdout 输出。"""
    import io
    from contextlib import redirect_stdout
    import importlib
    import scripts.run_official_monitor as cli_mod

    with patch.object(cli_mod, "run_official_monitor", return_value=mock_result):
        with redirect_stdout(io.StringIO()) as buf:
            sys.argv = ["run_official_monitor.py"] + args_list
            try:
                cli_mod.main()
            except SystemExit:
                pass
    return buf.getvalue()


def test_default_no_outside_window_in_output():
    """默认模式：窗口外 Blog 不出现在主输出。"""
    mock_result = _make_result(blog_in_window=1, blog_outside=2)
    output = _run_cli(
        ["--competitor", "Tavily", "--start-date", "2026-07-08",
         "--end-date", "2026-07-17", "--sources", "all",
         "--disable-querit-supplement"],
        mock_result,
    )
    # 窗口外 Blog 标题不应出现在主输出（只有数量统计）
    assert "Old Blog" not in output
    # 应包含窗口外数量提示
    assert "窗口外" in output or "outside" in output.lower() or "show-outside-window" in output


def test_default_shows_inwindow_blog():
    """默认模式：窗口内 Blog 必须出现。"""
    mock_result = _make_result(blog_in_window=1, blog_outside=0)
    output = _run_cli(
        ["--competitor", "Tavily", "--start-date", "2026-07-08",
         "--end-date", "2026-07-17", "--disable-querit-supplement"],
        mock_result,
    )
    assert "Keyless Search Blog" in output


def test_show_outside_window_flag_shows_all():
    """--show-outside-window 时，窗口外 Blog 也出现。"""
    mock_result = _make_result(blog_in_window=1, blog_outside=2)
    output = _run_cli(
        ["--competitor", "Tavily", "--start-date", "2026-07-08",
         "--end-date", "2026-07-17", "--disable-querit-supplement",
         "--show-outside-window"],
        mock_result,
    )
    assert "Old Blog" in output


def test_github_events_always_shown():
    """GitHub 聚合事件无论是否 --show-outside-window 都显示。"""
    mock_result = _make_result(blog_in_window=0, blog_outside=0, github_events=1)
    output = _run_cli(
        ["--competitor", "Tavily", "--start-date", "2026-07-08",
         "--end-date", "2026-07-17", "--disable-querit-supplement"],
        mock_result,
    )
    assert "tavily-mcp" in output.lower() or "streaming" in output.lower()


def test_benchmark_hit_detection():
    """基准关键词命中逻辑不因过滤而失效。"""
    mock_result = _make_result(blog_in_window=1, blog_outside=0, github_events=1)
    output = _run_cli(
        ["--competitor", "Tavily", "--start-date", "2026-07-08",
         "--end-date", "2026-07-17", "--disable-querit-supplement"],
        mock_result,
    )
    assert "[HIT]" in output
    assert "Keyless Search" in output
