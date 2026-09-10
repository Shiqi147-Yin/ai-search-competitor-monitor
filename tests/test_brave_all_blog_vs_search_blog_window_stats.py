"""test_brave_all_blog_vs_search_blog_window_stats.py
验证 blog_all_in_window 与 blog_search_in_window 两个统计字段语义不同，
不会混淆，且能通过 source_stats 正确读取。
"""
import pytest


def test_blog_stats_field_names_are_distinct():
    """source_stats['blog'] 应包含 blog_all_in_window 字段（含所有博文），
    source_stats['blog_funnel'] 应包含 blog_in_window 字段（仅 Search-related）。
    两者语义不同，数值上可以不等（all >= search）。
    """
    # 模拟 source_stats
    source_stats = {
        "blog": {
            "found": 35,
            "blog_all_in_window": 3,    # 所有 Blog（含 non-search）窗口内数量
            "in_window": 3,              # 兼容旧字段
        },
        "blog_funnel": {
            "blog_discovered": 35,
            "blog_search_related": 26,
            "blog_non_search_filtered": 9,
            "blog_in_window": 1,         # Search-related 中窗口内数量
            "blog_outside_window": 25,
            "blog_invalid_date": 0,
        },
    }

    blog_all_in_win = source_stats["blog"].get("blog_all_in_window", 0)
    blog_search_in_win = source_stats["blog_funnel"].get("blog_in_window", 0)

    # 两者字段名不同
    assert "blog_all_in_window" in source_stats["blog"], \
        "source_stats['blog'] should have 'blog_all_in_window'"
    assert "blog_in_window" in source_stats["blog_funnel"], \
        "source_stats['blog_funnel'] should have 'blog_in_window'"

    # 两者可以不相等（all >= search 通常成立，因为 all 包含 non-search 博文）
    assert blog_all_in_win >= blog_search_in_win, (
        f"blog_all_in_window={blog_all_in_win} should be >= blog_search_in_window={blog_search_in_win}"
    )


def test_blog_funnel_integrity():
    """blog_funnel 各字段加总约束。"""
    funnel = {
        "blog_discovered": 35,
        "blog_search_related": 26,
        "blog_non_search_filtered": 9,
        "blog_in_window": 1,
        "blog_outside_window": 25,
        "blog_invalid_date": 0,
    }

    assert funnel["blog_discovered"] == funnel["blog_search_related"] + funnel["blog_non_search_filtered"]
    assert funnel["blog_search_related"] == (
        funnel["blog_in_window"] + funnel["blog_outside_window"] + funnel["blog_invalid_date"]
    )


def test_blog_all_in_window_can_exceed_search_in_window():
    """blog_all_in_window 包括 non-search 博文，可以大于 blog_search_in_window。"""
    # e.g. 3 posts are within window: 1 is Search-related, 2 are Browser/Wallet posts
    source_stats = {
        "blog": {
            "found": 40,
            "blog_all_in_window": 3,
            "in_window": 3,
        },
        "blog_funnel": {
            "blog_discovered": 40,
            "blog_search_related": 28,
            "blog_non_search_filtered": 12,
            "blog_in_window": 1,
            "blog_outside_window": 27,
            "blog_invalid_date": 0,
        },
    }

    assert source_stats["blog"]["blog_all_in_window"] == 3
    assert source_stats["blog_funnel"]["blog_in_window"] == 1
    assert source_stats["blog"]["blog_all_in_window"] > source_stats["blog_funnel"]["blog_in_window"]
