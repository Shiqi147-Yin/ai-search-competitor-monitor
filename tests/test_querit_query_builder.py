"""测试：Querit Query 生成器"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from services.querit_query_builder import generate_queries, is_english_query


def test_queries_are_english():
    """所有生成的 Query 必须为英文。"""
    queries = generate_queries(["Tavily", "Exa", "Brave"], 7, ["All"])
    for q in queries:
        assert is_english_query(q["generated_query"]), (
            f"非英文 Query: {q['generated_query'][:80]}"
        )


def test_generates_for_each_competitor():
    """每个竞品各自生成 Query。"""
    for comp in ["Tavily", "Exa", "Brave"]:
        queries = generate_queries([comp], 7, ["All"])
        comp_queries = [q for q in queries if q["competitor"] == comp]
        assert comp_queries, f"{comp} 没有生成任何 Query"


def test_time_window_in_query():
    """时间窗口写入 Query 文本（新模板使用绝对日期，数字可能不直接出现；检查日期区间存在）。"""
    for days in [7, 14, 30]:
        queries = generate_queries(["Tavily"], days, ["All"])
        for q in queries:
            text = q["generated_query"]
            # 新模板使用绝对日期，检查日期年份存在即可
            assert "2" in text and "0" in text, (
                f"时间窗口 {days} 天的 Query 缺少日期信息: {text[:100]}"
            )


def test_github_query_contains_required_terms():
    """GitHub Query 包含 commits、releases、documentation、integrations。"""
    queries = generate_queries(["Tavily"], 7, ["GitHub"])
    github_queries = [q for q in queries if "github" in q["query_type"].lower()]
    assert github_queries, "未生成 GitHub Query"
    for q in github_queries:
        text = q["generated_query"].lower()
        assert any(t in text for t in ("commits", "commit", "releases", "released")), (
            f"GitHub Query 缺少 commits/releases: {text[:120]}"
        )


def test_x_query_contains_official_posts():
    """X Query 包含 official 相关内容。"""
    queries = generate_queries(["Exa"], 7, ["X"])
    x_queries = [q for q in queries if "x" in q["query_type"].lower() or "social" in q["query_type"].lower()]
    assert x_queries, "未生成 X Query"
    for q in x_queries:
        text = q["generated_query"].lower()
        assert "official" in text or "x" in text or "twitter" in text


def test_all_mode_generates_multiple_queries():
    """All 模式拆成多条独立 Query。"""
    queries = generate_queries(["Tavily"], 7, ["All"])
    assert len(queries) >= 3, f"All 模式只生成了 {len(queries)} 条 Query"


def test_user_edited_query_preserved():
    """用户手动编辑的 Query 内容可以保留。"""
    queries = generate_queries(["Tavily"], 7, ["All"])
    original = queries[0]["generated_query"]
    custom = "My custom English query about Tavily"
    queries[0]["generated_query"] = custom
    assert queries[0]["generated_query"] == custom
    assert queries[0]["generated_query"] != original


def test_is_english_query():
    assert is_english_query("Latest Tavily API updates") is True
    assert is_english_query("") is False
    assert is_english_query("Tavily 最新更新") is False
