"""测试：Query 绝对日期范围"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from datetime import datetime, timezone
from services.querit_query_builder import generate_queries, is_english_query, _format_date_range


def _ref():
    return datetime(2026, 7, 21, 12, 0, 0, tzinfo=timezone.utc)


def test_all_queries_contain_absolute_dates():
    """7/14/30 天 Query 均包含绝对日期。"""
    for days in [7, 14, 30]:
        queries = generate_queries(["Tavily"], days, ["All"], _ref())
        for q in queries:
            text = q["generated_query"].lower()
            assert "2026" in text, f"{days}天 Query 缺少年份: {text[:100]}"


def test_query_contains_published_between_or_date_range():
    """Query 包含 published between 或 between...and。"""
    queries = generate_queries(["Tavily"], 7, ["All"], _ref())
    for q in queries:
        text = q["generated_query"].lower()
        assert "between" in text or "july" in text, (
            f"Query 缺少日期范围表述: {text[:120]}"
        )


def test_query_contains_exclude_older():
    """Query 包含 exclude older content 或类似表述。"""
    queries = generate_queries(["Tavily"], 7, ["All"], _ref())
    for q in queries:
        text = q["generated_query"].lower()
        assert "exclude" in text or "published before" in text, (
            f"Query 缺少排除旧内容表述: {text[:120]}"
        )


def test_github_query_uses_committed_released():
    """GitHub Query 使用 committed or released 相关词汇。"""
    queries = generate_queries(["Exa"], 7, ["GitHub"], _ref())
    gh_queries = [q for q in queries if "github" in q["query_type"].lower()]
    assert gh_queries, "未生成 GitHub Query"
    for q in gh_queries:
        text = q["generated_query"].lower()
        assert "commit" in text or "released" in text or "github" in text, (
            f"GitHub Query 缺少 commit/released: {text[:120]}"
        )


def test_all_queries_are_english():
    """所有生成 Query 均为英文。"""
    queries = generate_queries(["Tavily", "Exa", "Brave"], 7, ["All"], _ref())
    for q in queries:
        assert is_english_query(q["generated_query"])


def test_date_range_format():
    """日期范围格式正确。"""
    dr = _format_date_range(7, _ref())
    assert dr["start_date"] == "July 14, 2026"
    assert dr["end_date"] == "July 21, 2026"
    assert dr["start_iso"] == "2026-07-14"
    assert dr["end_iso"] == "2026-07-21"
