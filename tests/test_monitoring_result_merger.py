"""test_monitoring_result_merger.py
验证官方结果优先、Querit 重复结果合并、官方日期不被覆盖、新线索保留。
"""
import pytest
from services.official_update_normalizer import OfficialUpdateItem
from services.monitoring_result_merger import merge_results, MergeResult


def _item(**kw):
    defaults = dict(
        competitor="Tavily", update_title="Test Item",
        update_date="2026-07-10", source_channel="website_blog",
        content_type="article", source_url="https://example.com/a",
        published_at="2026-07-10", updated_at="",
        discovery_method="official_direct",
    )
    defaults.update(kw)
    return OfficialUpdateItem(**defaults)


def test_official_items_preserved():
    official = [_item(source_url="https://tavily.com/blog/keyless", update_title="Keyless Search")]
    result = merge_results(official, [])
    assert len(result.official_items) == 1
    assert result.official_items[0].update_title == "Keyless Search"


def test_querit_duplicate_url_merged():
    """Querit 与官方 URL 一致时合并，discovery_method 变为 both。"""
    official = [_item(source_url="https://tavily.com/blog/keyless", update_title="Keyless Search")]
    querit = [_item(source_url="https://tavily.com/blog/keyless", update_title="Keyless Search Article",
                    discovery_method="querit_supplement")]
    result = merge_results(official, querit)
    assert result.merged_count == 1
    assert result.official_items[0].discovery_method == "both"
    assert len(result.querit_supplement) == 0


def test_querit_similar_title_merged():
    """Querit 与官方标题高度相似时合并。"""
    official = [_item(source_url="https://tavily.com/blog/nemo", update_title="NVIDIA NeMo Deep Agents Integration")]
    querit = [_item(source_url="https://other.com/nemo", update_title="NeMo Deep Agents Tavily Integration",
                    discovery_method="querit_supplement")]
    result = merge_results(official, querit, title_threshold=0.5)
    assert result.merged_count == 1


def test_querit_new_lead_kept_as_supplement():
    """Querit 独有新线索保留在 querit_supplement。"""
    official = [_item(source_url="https://tavily.com/blog/keyless", update_title="Keyless Search")]
    querit = [_item(source_url="https://luma.com/event/dev-cup", update_title="Composio Dev Cup Tavily",
                    discovery_method="querit_supplement")]
    result = merge_results(official, querit)
    assert len(result.querit_supplement) == 1
    assert result.querit_supplement[0].discovery_method == "querit_supplement"


def test_querit_does_not_overwrite_official_published_at():
    """合并后官方的 published_at 不被 Querit 覆盖。"""
    official = [_item(source_url="https://tavily.com/blog/keyless",
                      published_at="2026-07-14", update_title="Keyless Search")]
    querit = [_item(source_url="https://tavily.com/blog/keyless",
                    published_at="2026-01-01",  # 错误日期
                    update_title="Keyless Search",
                    discovery_method="querit_supplement")]
    result = merge_results(official, querit)
    assert result.official_items[0].published_at == "2026-07-14"


def test_empty_querit_returns_official_unchanged():
    official = [_item(), _item(source_url="https://example.com/b")]
    result = merge_results(official, [])
    assert len(result.official_items) == 2
    assert len(result.querit_supplement) == 0
    assert result.merged_count == 0
