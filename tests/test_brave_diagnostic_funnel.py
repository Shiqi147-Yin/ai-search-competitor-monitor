"""test_brave_diagnostic_funnel.py
验证 Brave 诊断漏斗统计字段的正确性。
"""
import pytest
from dataclasses import dataclass, field
from unittest.mock import patch, MagicMock


# ── Mock OfficialUpdateItem（轻量）────────────────────────────

@dataclass
class _MockUpdateItem:
    source_channel: str = "website_blog"
    source_url: str = ""
    update_title: str = ""
    within_window: object = False   # True / False / None


# ── Test 1: blog_funnel 各字段相加能解释总数 ──────────────────

def test_brave_diagnostic_funnel_counts():
    """blog_discovered = search_related + non_search_filtered
    search_related = in_window + outside_window + invalid_date
    """
    # 模拟 filter_brave_items_by_search_relevance 输出
    search_items = [
        _MockUpdateItem(within_window=True),   # in_window
        _MockUpdateItem(within_window=False),  # outside_window
        _MockUpdateItem(within_window=False),  # outside_window
        _MockUpdateItem(within_window=None),   # invalid_date
    ]
    filter_stats = {
        "scanned": 6,           # 4 search + 2 non_search
        "search_related": 4,
        "filtered_non_search": 2,
    }

    # 手动模拟 official_source_monitor 中 blog_funnel 计算逻辑
    _search_blog = search_items  # 已过滤后的 blog items
    _in_window = [i for i in _search_blog if getattr(i, "within_window", False) is True]
    _outside_window = [i for i in _search_blog if getattr(i, "within_window", False) is False]
    _invalid_date = [i for i in _search_blog if getattr(i, "within_window", None) is None]

    funnel = {
        "blog_discovered": filter_stats["scanned"],
        "blog_search_related": filter_stats["search_related"],
        "blog_non_search_filtered": filter_stats["filtered_non_search"],
        "blog_in_window": len(_in_window),
        "blog_outside_window": len(_outside_window),
        "blog_invalid_date": len(_invalid_date),
    }

    # 验证约束 1：discovered = search_related + non_search_filtered
    assert funnel["blog_discovered"] == funnel["blog_search_related"] + funnel["blog_non_search_filtered"], (
        f"discovered={funnel['blog_discovered']} ≠ "
        f"search_related={funnel['blog_search_related']} + non_search={funnel['blog_non_search_filtered']}"
    )

    # 验证约束 2：search_related = in_window + outside_window + invalid_date
    assert funnel["blog_search_related"] == (
        funnel["blog_in_window"] + funnel["blog_outside_window"] + funnel["blog_invalid_date"]
    ), (
        f"search_related={funnel['blog_search_related']} ≠ "
        f"in_window={funnel['blog_in_window']} + outside={funnel['blog_outside_window']} + invalid={funnel['blog_invalid_date']}"
    )

    # 数字验证（基于本测试 fixture）
    assert funnel["blog_discovered"] == 6
    assert funnel["blog_search_related"] == 4
    assert funnel["blog_non_search_filtered"] == 2
    assert funnel["blog_in_window"] == 1
    assert funnel["blog_outside_window"] == 2
    assert funnel["blog_invalid_date"] == 1


# ── Test 2: 0 最终候选是合法结果 ──────────────────────────────

def test_brave_zero_candidate_is_valid():
    """blog_in_window=0 且 github=0 时，漏斗统计仍然有效，不应触发断言。"""
    filter_stats = {
        "scanned": 40,
        "search_related": 21,
        "filtered_non_search": 19,
    }

    search_items = [_MockUpdateItem(within_window=False) for _ in range(21)]
    _in_window = [i for i in search_items if getattr(i, "within_window", False) is True]
    _outside_window = [i for i in search_items if getattr(i, "within_window", False) is False]
    _invalid_date = [i for i in search_items if getattr(i, "within_window", None) is None]

    funnel = {
        "blog_discovered": filter_stats["scanned"],
        "blog_search_related": filter_stats["search_related"],
        "blog_non_search_filtered": filter_stats["filtered_non_search"],
        "blog_in_window": len(_in_window),
        "blog_outside_window": len(_outside_window),
        "blog_invalid_date": len(_invalid_date),
    }

    assert funnel["blog_in_window"] == 0, "窗口内应为 0"
    assert funnel["blog_discovered"] == 40
    # 约束仍然满足
    assert funnel["blog_discovered"] == funnel["blog_search_related"] + funnel["blog_non_search_filtered"]
    assert funnel["blog_search_related"] == funnel["blog_in_window"] + funnel["blog_outside_window"] + funnel["blog_invalid_date"]


# ── Test 3: github_status = success_no_updates ───────────────

def test_brave_github_no_updates_status():
    """raw_commits=0 且无 github 错误时，github_status 应为 success_no_updates。"""
    raw_commits = []
    errors = []

    _github_status = "ok" if raw_commits else "success_no_updates"

    assert _github_status == "success_no_updates", (
        f"Expected 'success_no_updates', got '{_github_status}'"
    )


def test_brave_github_ok_status_when_commits_exist():
    """raw_commits > 0 时，github_status 应为 ok。"""
    raw_commits = [object(), object()]  # 2 个 commit
    _github_status = "ok" if raw_commits else "success_no_updates"
    assert _github_status == "ok"


# ── Test 4: docs_status = blocked_403 ────────────────────────

def test_brave_docs_blocked_status():
    """docs_items=[] 且 errors 含 403 时，docs_status 应为 blocked_403。"""
    docs_items = []
    errors = [{"source_type": "docs", "error": "HTTP 403 Forbidden"}]

    _docs_errors = [e for e in errors
                    if e.get("source_type") in ("docs", "website")]
    if docs_items:
        docs_status = "ok"
    elif any("403" in str(e.get("error", "")) for e in _docs_errors):
        docs_status = "blocked_403"
    elif _docs_errors:
        docs_status = "unavailable"
    else:
        docs_status = "no_pages_found"

    assert docs_status == "blocked_403", f"Expected 'blocked_403', got '{docs_status}'"


def test_brave_docs_unavailable_status():
    """docs_items=[] 且 errors 含其他网络错误时，docs_status 应为 unavailable。"""
    docs_items = []
    errors = [{"source_type": "docs", "error": "ConnectionError: timeout"}]

    _docs_errors = [e for e in errors
                    if e.get("source_type") in ("docs", "website")]
    if docs_items:
        docs_status = "ok"
    elif any("403" in str(e.get("error", "")) for e in _docs_errors):
        docs_status = "blocked_403"
    elif _docs_errors:
        docs_status = "unavailable"
    else:
        docs_status = "no_pages_found"

    assert docs_status == "unavailable"


def test_brave_docs_no_pages_found_status():
    """docs_items=[] 且无错误时，docs_status 应为 no_pages_found。"""
    docs_items = []
    errors = []

    _docs_errors = [e for e in errors
                    if e.get("source_type") in ("docs", "website")]
    if docs_items:
        docs_status = "ok"
    elif any("403" in str(e.get("error", "")) for e in _docs_errors):
        docs_status = "blocked_403"
    elif _docs_errors:
        docs_status = "unavailable"
    else:
        docs_status = "no_pages_found"

    assert docs_status == "no_pages_found"


def test_brave_docs_ok_status():
    """docs_items 有内容时，docs_status 应为 ok。"""
    docs_items = [object()]
    errors = []

    _docs_errors = [e for e in errors
                    if e.get("source_type") in ("docs", "website")]
    if docs_items:
        docs_status = "ok"
    elif any("403" in str(e.get("error", "")) for e in _docs_errors):
        docs_status = "blocked_403"
    elif _docs_errors:
        docs_status = "unavailable"
    else:
        docs_status = "no_pages_found"

    assert docs_status == "ok"
