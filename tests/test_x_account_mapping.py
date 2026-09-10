"""测试：X 账号映射（从 official_accounts.yaml 读取）"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
from services.source_detector import detect_competitor, invalidate_account_cache


@pytest.fixture(autouse=True)
def clear_cache():
    invalidate_account_cache()
    yield
    invalidate_account_cache()


def test_exa_developers_is_exa():
    """ExaDevelopers 账号 → Exa。"""
    result = detect_competitor("https://x.com/ExaDevelopers/status/2077438984775733583")
    assert result == "Exa"


def test_exa_ailabs_is_exa():
    """ExaAILabs 账号 → Exa。"""
    result = detect_competitor("https://x.com/ExaAILabs/status/123456")
    assert result == "Exa"


def test_tavily_account_is_tavily():
    """已配置的 Tavily X 账号 → Tavily。"""
    # TavilyHQ / TavilyAI 中任意一个
    for handle in ["TavilyHQ", "TavilyAI", "tavily_ai"]:
        result = detect_competitor(f"https://x.com/{handle}/status/123")
        assert result == "Tavily", f"账号 {handle} 应识别为 Tavily，实际为 {result}"


def test_brave_search_account_is_brave():
    """BraveSearch 账号 → Brave。"""
    result = detect_competitor("https://x.com/BraveSearch/status/999")
    assert result == "Brave"


def test_unknown_x_account_is_other():
    """未配置的账号 → Other。"""
    result = detect_competitor("https://x.com/randomAccount123/status/456")
    assert result == "Other"


def test_twitter_url_also_works():
    """twitter.com URL 也能识别。"""
    result = detect_competitor("https://twitter.com/ExaDevelopers/status/123")
    assert result == "Exa"


def test_x_platform_correct():
    """X 平台识别正确。"""
    from services.source_detector import detect_platform
    assert detect_platform("https://x.com/ExaDevelopers/status/123") == "X"
    assert detect_platform("https://twitter.com/TavilyHQ") == "X"
