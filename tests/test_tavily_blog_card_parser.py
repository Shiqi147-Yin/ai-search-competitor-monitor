"""测试：Tavily Blog 卡片日期解析"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from services.source_drilldown import _parse_blog_card_date


def test_keyless_search_date_extracted():
    """标准卡片：标题+类别+月日"""
    text = "What Keyless Search Really Means for Your Dataproduct·Jul 14"
    date, title = _parse_blog_card_date(text, "2026-07-21T00:00:00Z")
    assert date == "2026-07-14T00:00:00Z", f"日期错误: {date}"
    assert "product" not in title.lower(), f"类别未去除: {title}"
    assert "Jul" not in title, f"月份未去除: {title}"
    assert "14" not in title, f"日期数字未去除: {title}"


def test_date_with_year():
    """包含年份的日期"""
    text = "Some Title Jul 14, 2026"
    date, _ = _parse_blog_card_date(text, "2026-07-21T00:00:00Z")
    assert "2026-07-14" in date


def test_june_shipped_date():
    """Jun 1, 2026"""
    text = "What We Shipped: June 2026news·Jun 1, 2026"
    date, title = _parse_blog_card_date(text, "2026-07-21T00:00:00Z")
    assert "2026-06-01" in date
    assert "shipped" in title.lower() or "june" in title.lower() or "what we" in title.lower()


def test_year_inferred_from_window():
    """无年份时从 window_end 推断年份"""
    text = "Some Article Jul 14"
    date, _ = _parse_blog_card_date(text, "2026-07-21T00:00:00Z")
    assert "2026" in date
    assert "07-14" in date


def test_title_cleaned_of_category():
    """标题中的分类词被去除"""
    text = "How Fieldway Built a Product Research Agent With Tavilycustomer·Apr 30"
    date, title = _parse_blog_card_date(text, "2026-07-21T00:00:00Z")
    # 日期应被提取
    assert "04-30" in date or "2026" in date
    # 标题不应含 customer
    assert "customer" not in title.lower()


def test_empty_text_returns_empty():
    date, title = _parse_blog_card_date("", "2026-07-21T00:00:00Z")
    assert date == ""
    assert title == ""


def test_no_date_returns_original_text():
    text = "Normal title without any date"
    date, title = _parse_blog_card_date(text, "2026-07-21T00:00:00Z")
    assert date == ""
    assert title == text
