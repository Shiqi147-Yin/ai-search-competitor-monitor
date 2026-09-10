"""测试：分来源定向 Query 生成"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from datetime import datetime, timezone
from services.querit_query_builder import generate_queries, is_english_query


def _ref():
    return datetime(2026, 7, 17, 12, 0, 0, tzinfo=timezone.utc)


def test_blog_query_contains_tavily_domain():
    queries = generate_queries(["Tavily"], 9, ["Blog"], _ref())
    blog_queries = [q for q in queries if "blog" in q["query_type"]]
    assert blog_queries, "未生成 Blog Query"
    for q in blog_queries:
        text = q["generated_query"].lower()
        assert "tavily.com" in text or "tavily" in text


def test_docs_query_contains_docs_domain():
    queries = generate_queries(["Tavily"], 9, ["Docs"], _ref())
    docs_queries = [q for q in queries if "docs" in q["query_type"]]
    assert docs_queries, "未生成 Docs Query"
    for q in docs_queries:
        text = q["generated_query"].lower()
        assert "docs.tavily.com" in text or "documentation" in text


def test_github_query_contains_github_owner():
    queries = generate_queries(["Tavily"], 9, ["GitHub"], _ref())
    gh_queries = [q for q in queries if "github" in q["query_type"]]
    assert gh_queries, "未生成 GitHub Query"
    for q in gh_queries:
        text = q["generated_query"].lower()
        assert "github.com/tavily-ai" in text or "github.com" in text


def test_event_query_contains_luma():
    queries = generate_queries(["Tavily"], 9, ["Event"], _ref())
    ev_queries = [q for q in queries if "event" in q["query_type"]]
    assert ev_queries, "未生成 Event Query"
    for q in ev_queries:
        text = q["generated_query"].lower()
        assert "luma.com" in text or "event" in text


def test_all_queries_contain_absolute_dates():
    queries = generate_queries(["Tavily"], 9, ["All"], _ref())
    for q in queries:
        text = q["generated_query"]
        assert "2026" in text, f"Query 缺少年份: {text[:100]}"


def test_all_queries_exclude_old_content():
    queries = generate_queries(["Tavily"], 9, ["All"], _ref())
    for q in queries:
        text = q["generated_query"].lower()
        assert "exclude" in text or "only" in text or "between" in text


def test_all_queries_are_english():
    queries = generate_queries(["Tavily", "Exa", "Brave"], 7, ["All"], _ref())
    for q in queries:
        assert is_english_query(q["generated_query"])


def test_all_mode_generates_multiple_queries():
    queries = generate_queries(["Tavily"], 7, ["All"], _ref())
    assert len(queries) >= 3
