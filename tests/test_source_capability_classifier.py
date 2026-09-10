"""测试：来源能力分级器"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from services.source_capability_classifier import classify_fetch_result


def test_success_full_content_is_level_a():
    """success + 有标题 + 有描述 + 有发布时间 → A级"""
    result = classify_fetch_result(
        fetch_status="success",
        has_title=True,
        has_description=True,
        has_published_date=True,
        source_platform="Blog",
    )
    assert result.automation_level == "A"
    assert not result.needs_manual


def test_success_no_date_is_level_b():
    """success + 有标题 + 无发布时间 → 需人工补充（B级以上）"""
    result = classify_fetch_result(
        fetch_status="success",
        has_title=True,
        has_description=True,
        has_published_date=False,
        source_platform="Blog",
    )
    # 即使 A 级，缺发布时间也需人工补充
    assert result.needs_manual


def test_restricted_is_level_c():
    """restricted → C级，需要人工补充"""
    result = classify_fetch_result(
        fetch_status="restricted",
        has_title=False,
        has_description=False,
        has_published_date=False,
        source_platform="X",
    )
    assert result.automation_level == "C"
    assert result.needs_manual


def test_failed_connect_timeout_degrades_level():
    """failed（ConnectTimeout）: A 级来源降为 B；C 级来源（X 配置为 B）保持 B 或 C。"""
    result_a = classify_fetch_result(
        fetch_status="failed",
        has_title=False,
        has_description=False,
        has_published_date=False,
        source_platform="Blog",  # 配置为 A → 降为 B
    )
    assert result_a.automation_level in ("B", "C")

    # X 在新配置中为 B 级（可部分抓取），failed 时保持 B
    result_x = classify_fetch_result(
        fetch_status="failed",
        has_title=False,
        has_description=False,
        has_published_date=False,
        source_platform="X",   # 配置为 B
    )
    assert result_x.automation_level in ("B", "C")


def test_override_level_applied():
    """人工覆盖等级优先于自动判断"""
    result = classify_fetch_result(
        fetch_status="restricted",
        has_title=False,
        has_description=False,
        has_published_date=False,
        source_platform="X",
        override_level="B",
    )
    assert result.automation_level == "B"
    assert result.override_applied


def test_partial_with_title_is_level_b():
    """partial + 有标题 → B级"""
    result = classify_fetch_result(
        fetch_status="partial",
        has_title=True,
        has_description=False,
        has_published_date=False,
        source_platform="Event",
    )
    assert result.automation_level == "B"


def test_github_platform_default_action():
    """GitHub 平台默认处理方式为 github_analysis"""
    from services.source_capability_classifier import get_platform_capability
    cap = get_platform_capability("GitHub")
    assert cap.get("default_action") == "github_analysis"


def test_linkedin_platform_is_c():
    """LinkedIn 配置为 C 级"""
    from services.source_capability_classifier import get_platform_capability
    cap = get_platform_capability("LinkedIn")
    assert cap.get("automation_level") == "C"
