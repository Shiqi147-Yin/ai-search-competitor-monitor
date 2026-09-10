"""测试：灵活 Excel 导入"""
import io
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import openpyxl
import pytest

from services.flexible_excel_importer import (
    detect_excel_type,
    parse_simple_url_table,
    parse_flexible_excel,
)
import pandas as pd


def _make_xlsx(headers: list[str], rows: list[list]) -> bytes:
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(headers)
    for row in rows:
        ws.append(row)
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def test_url_only_column_recognized():
    """只有 URL 一列的 Excel 应被识别为 simple_url_table。"""
    xlsx = _make_xlsx(["URL"], [["https://tavily.com/blog/1"], ["https://exa.ai/post"]])
    records, excel_type, errors = parse_flexible_excel(xlsx)
    assert excel_type == "simple_url_table"
    assert len(records) == 2
    assert not errors


def test_various_url_column_names():
    """链接/原始链接/url/link 等列名均应被识别。"""
    for col_name in ["链接", "原始链接", "url", "link", "source_url", "Link"]:
        xlsx = _make_xlsx([col_name], [["https://example.com/page"]])
        records, excel_type, errors = parse_flexible_excel(xlsx)
        assert excel_type == "simple_url_table", f"列名 '{col_name}' 未被识别"
        assert len(records) >= 1


def test_simple_table_with_optional_columns():
    """带可选列的简单表应能解析，字段正确映射。"""
    xlsx = _make_xlsx(
        ["原始链接", "竞品", "发布时间", "标题"],
        [["https://tavily.com/blog/2", "Tavily", "2026-07-10", "New API"]]
    )
    records, excel_type, errors = parse_flexible_excel(xlsx)
    assert excel_type == "simple_url_table"
    assert records[0]["competitor"] == "Tavily"
    assert records[0]["title"] == "New API"


def test_full_template_still_works():
    """原有完整模板仍可被正确识别和解析。"""
    full_headers = ["发布时间", "竞品", "动态标题", "动态概述", "原始链接", "信息平台", "备注"]
    xlsx = _make_xlsx(
        full_headers,
        [["2026-07-01", "Exa", "Exa Update", "Summary", "https://exa.ai/blog/1", "官网", ""]]
    )
    records, excel_type, errors = parse_flexible_excel(xlsx)
    assert excel_type == "full_template"
    assert len(records) >= 1


def test_no_url_column_returns_error():
    """缺少链接列时应返回明确中文错误，不抛异常。"""
    xlsx = _make_xlsx(["名称", "描述"], [["Tavily", "Some text"]])
    records, excel_type, errors = parse_flexible_excel(xlsx)
    assert excel_type == "unknown" or len(errors) > 0
    assert any("链接" in e or "URL" in e or "格式" in e for e in errors)


def test_duplicate_url_not_imported(tmp_path, monkeypatch):
    """重复 URL 不应重复导入（通过 DB 去重）。"""
    import config, database
    from services.data_service import batch_insert
    from services.excel_importer import enrich_records

    tmp_db = tmp_path / "flex_test.db"
    monkeypatch.setattr(config, "DB_PATH", tmp_db)
    monkeypatch.setattr(database, "DB_PATH", tmp_db)
    database.init_db()
    database.migrate_db()

    # 先插入一条
    database.insert_record({"title": "existing", "source_url": "https://example.com/dup-flex",
                             "normalized_url": "https://example.com/dup-flex"})

    xlsx = _make_xlsx(["URL"], [["https://example.com/dup-flex"]])
    records, excel_type, errors = parse_flexible_excel(xlsx)
    assert excel_type == "simple_url_table"

    # 导入应识别为重复
    from services.url_normalizer import normalize_url
    url = records[0]["source_url"]
    is_dup = database.is_url_duplicate(normalize_url(url))
    assert is_dup
