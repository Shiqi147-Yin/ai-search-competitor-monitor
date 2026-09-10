"""测试：Excel 解析服务"""
import io
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pandas as pd
import openpyxl
import pytest

from services.excel_importer import parse_excel, enrich_records, validate_required_columns
from config import EXCEL_REQUIRED_COLUMNS


def _make_xlsx(rows: list[dict], headers: list[str] | None = None) -> bytes:
    """构造一个内存中的 xlsx 文件字节流。"""
    if headers is None:
        headers = ["发布时间", "竞品", "动态标题", "动态概述", "原始链接", "信息平台", "备注"]
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(headers)
    for row in rows:
        ws.append([row.get(h, "") for h in headers])
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def test_parse_correct_excel():
    """正确 Excel 应成功解析，行数与输入一致。"""
    data = [
        {
            "发布时间": "2026-07-15",
            "竞品": "Tavily",
            "动态标题": "测试标题",
            "动态概述": "摘要内容",
            "原始链接": "https://example.com/1",
            "信息平台": "官网",
            "备注": "",
        }
    ]
    xlsx_bytes = _make_xlsx(data)
    df, errors = parse_excel(xlsx_bytes)
    assert df is not None, f"解析不应失败，errors={errors}"
    assert len(df) == 1
    # 只有日期/必填错误才算真实错误
    critical_errors = [e for e in errors if "不能为空" in e or "格式有误" in e]
    assert not critical_errors, f"不应有关键错误：{critical_errors}"


def test_parse_missing_required_column():
    """缺少必须列时应返回 None 和明确错误。"""
    # 去掉"动态标题"列
    headers = ["发布时间", "竞品", "动态概述", "原始链接", "信息平台", "备注"]
    xlsx_bytes = _make_xlsx([], headers=headers)
    df, errors = parse_excel(xlsx_bytes)
    assert df is None
    assert any("动态标题" in e or "缺少必须列" in e for e in errors), f"应提示缺失列，errors={errors}"


def test_parse_invalid_date():
    """错误日期格式应被识别，并在 errors 中标注行号。"""
    data = [
        {
            "发布时间": "not-a-date",
            "竞品": "Exa",
            "动态标题": "日期错误测试",
            "动态概述": "",
            "原始链接": "https://example.com/2",
            "信息平台": "Blog",
            "备注": "",
        }
    ]
    xlsx_bytes = _make_xlsx(data)
    df, errors = parse_excel(xlsx_bytes)
    date_errors = [e for e in errors if "格式有误" in e or "发布时间" in e]
    assert date_errors, f"应有日期格式错误提示，errors={errors}"


def test_duplicate_url_skipped_on_import(tmp_path, monkeypatch):
    """重复 URL 的行在批量导入时应跳过并计入 duplicate。"""
    import config, database
    from services.data_service import batch_insert

    tmp_db = tmp_path / "test_dup_import.db"
    monkeypatch.setattr(config, "DB_PATH", tmp_db)
    monkeypatch.setattr(database, "DB_PATH", tmp_db)
    database.init_db()

    data = [
        {
            "发布时间": "2026-07-10",
            "竞品": "Brave",
            "动态标题": "首次导入",
            "动态概述": "",
            "原始链接": "https://example.com/dup_import",
            "信息平台": "GitHub",
            "备注": "",
        }
    ]
    xlsx_bytes = _make_xlsx(data)
    df, _ = parse_excel(xlsx_bytes)
    df_enriched = enrich_records(df)
    records = df_enriched.to_dict(orient="records")

    result1 = batch_insert(records)
    assert result1["success"] == 1

    result2 = batch_insert(records)
    assert result2["duplicate"] == 1
    assert result2["success"] == 0
