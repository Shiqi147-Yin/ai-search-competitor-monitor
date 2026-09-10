"""测试：相关性过滤器"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from services.competitor_relevance_filter import classify_source_authority, classify_relevance


def test_official_blog_is_official():
    auth, official = classify_source_authority("https://tavily.com/blog/keyless", "Tavily")
    assert auth == "official"
    assert official is True


def test_official_github_is_official():
    auth, official = classify_source_authority("https://github.com/tavily-ai/tavily-mcp/releases", "Tavily")
    assert auth == "official"
    assert official is True


def test_luma_tavily_is_ecosystem():
    auth, official = classify_source_authority("https://luma.com/tavily-h550", "Tavily")
    assert auth == "first_party_ecosystem"
    assert official is False


def test_advfn_is_low_value():
    auth, official = classify_source_authority("https://advfn.com/news/tavily", "Tavily")
    assert auth == "low_value_aggregator"
    assert official is False


def test_github_topics_is_reputable_third_party():
    auth, official = classify_source_authority("https://github.com/topics/tavily", "Tavily")
    assert auth == "reputable_third_party"
    assert official is False


def test_official_blog_exact_match_gets_exact_target():
    rec = {"source_url": "https://tavily.com/blog/post"}
    result = classify_relevance(rec, "Tavily", "exact_url", 1.0)
    assert result["target_match_status"] == "exact_target"
    assert result["official_source"] is True


def test_low_value_aggregator_default_not_selected():
    rec = {"source_url": "https://advfn.com/article"}
    result = classify_relevance(rec, "Tavily", "no_match", 0.0)
    assert result["default_selected"] is False
    assert result["source_authority"] == "low_value_aggregator"


def test_third_party_mcp_default_not_selected():
    rec = {"source_url": "https://mcpshowcase.com/servers/tavily"}
    result = classify_relevance(rec, "Tavily", "no_match", 0.0)
    assert result["default_selected"] is False
