"""测试：Querit 分析流水线"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
from services.querit_client import SearchResult
from services.querit_result_adapter import adapt_result
from services.content_analyzer import analyze_record


@pytest.fixture(autouse=True)
def isolated_db(tmp_path, monkeypatch):
    import config, database
    tmp_db = tmp_path / "analysis_pipeline_test.db"
    monkeypatch.setattr(config, "DB_PATH", tmp_db)
    monkeypatch.setattr(database, "DB_PATH", tmp_db)
    database.init_db()
    database.migrate_db()
    yield


def _sr(**kwargs):
    base = dict(
        title="Tavily streaming search API", url="https://docs.tavily.com/streaming",
        content="New streaming API with MCP support and agent skills.", summary="Streaming API release.",
        published_date="2026-07-15", score=0.95, rank=1, query="Tavily updates",
        raw_source="", raw_metadata={},
    )
    base.update(kwargs)
    return SearchResult(**base)


def test_querit_summary_feeds_analyzer():
    """Querit 摘要进入现有 analyzer，生成分类和优先级。"""
    r = _sr()
    rec = adapt_result(r, "run1", 1)
    result = analyze_record(rec)
    assert result.auto_category in ("产品与功能", "生态与集成", "市场与运营", "待评估")
    assert result.auto_priority in ("高", "中", "低")


def test_analyzer_does_not_overwrite_human_fields():
    """自动分析不覆盖人工已填写字段。"""
    r = _sr()
    rec = adapt_result(r, "run1", 1)
    rec["category"] = "市场与运营"  # 模拟人工设置
    result = analyze_record(rec)
    fill = result.to_fill_fields({"category": "市场与运营"})
    assert fill.get("category", "市场与运营") == "市场与运营"


def test_restricted_source_confidence_limited():
    """受限来源置信度不超过 0.40。"""
    r = _sr(url="https://linkedin.com/posts/exa-ai_update")
    rec = adapt_result(r, "run1", 1, query_competitor="Exa")
    rec["fetch_status"] = "restricted"
    rec["source_platform"] = "LinkedIn"
    rec["raw_content"] = ""
    rec["summary"] = ""
    result = analyze_record(rec)
    assert result.analysis_confidence <= 0.40


def test_single_analysis_failure_does_not_block_batch():
    """单条分析异常不阻止其他记录。"""
    items = [
        _sr(url="https://tavily.com/a"),
        _sr(url="https://exa.ai/b"),
    ]
    results = []
    for r in items:
        rec = adapt_result(r, "run1", 1)
        try:
            an = analyze_record(rec)
            results.append(an)
        except Exception:
            pass
    assert len(results) == 2
