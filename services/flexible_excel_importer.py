"""灵活 Excel 导入：自动识别完整模板或简单链接表"""
import io
from typing import Optional

import pandas as pd

from config import EXCEL_COLUMN_MAP, EXCEL_REQUIRED_COLUMNS

# 简单链接表支持的列名（不区分大小写）
_URL_COLUMN_ALIASES = {"链接", "原始链接", "url", "link", "source_url", "源链接"}

# 简单表可选附加列及其映射
_SIMPLE_OPTIONAL_MAP = {
    "竞品": "competitor",
    "发布时间": "publish_date",
    "标题": "title",
    "动态标题": "title",
    "动态概述": "summary",
    "摘要": "summary",
    "信息平台": "source_platform",
    "备注": "gap_analysis",
}


def _normalize_col(col: str) -> str:
    return str(col).strip().lower()


def detect_excel_type(df: pd.DataFrame) -> str:
    """判断 Excel 类型。
    Returns: 'full_template' | 'simple_url_table' | 'unknown'
    """
    cols_lower = {_normalize_col(c) for c in df.columns}

    # 完整模板：必须包含全部 7 个标准列
    required_lower = {_normalize_col(c) for c in EXCEL_REQUIRED_COLUMNS}
    if required_lower.issubset(cols_lower):
        return "full_template"

    # 简单链接表：只需包含一个可识别的 URL 列
    for col in cols_lower:
        if col in {a.lower() for a in _URL_COLUMN_ALIASES}:
            return "simple_url_table"

    return "unknown"


def _find_url_column(df: pd.DataFrame) -> Optional[str]:
    """找到 DataFrame 中的 URL 列名（原始大小写）。"""
    aliases_lower = {a.lower() for a in _URL_COLUMN_ALIASES}
    for col in df.columns:
        if _normalize_col(col) in aliases_lower:
            return col
    return None


def parse_simple_url_table(df: pd.DataFrame) -> tuple[list[dict], list[str]]:
    """解析简单链接表，返回 (records, errors)。"""
    errors: list[str] = []

    url_col = _find_url_column(df)
    if url_col is None:
        return [], ["未找到链接列，支持列名：链接、原始链接、URL、url、Link、link、source_url"]

    # 删除全空行
    df = df.dropna(how="all").reset_index(drop=True)

    records: list[dict] = []
    for idx, row in df.iterrows():
        url_val = str(row[url_col]).strip() if pd.notna(row[url_col]) else ""
        if not url_val or url_val == "nan":
            continue  # 跳过空 URL 行

        rec: dict = {"source_url": url_val}

        # 映射可选列
        for raw_col, db_col in _SIMPLE_OPTIONAL_MAP.items():
            for df_col in df.columns:
                if _normalize_col(df_col) == _normalize_col(raw_col):
                    val = row.get(df_col)
                    if pd.notna(val) and str(val).strip() not in ("", "nan"):
                        rec[db_col] = str(val).strip()
                    break

        records.append(rec)

    if not records:
        errors.append("链接表中没有找到有效 URL")

    return records, errors


def parse_flexible_excel(file_bytes: bytes) -> tuple[list[dict], str, list[str]]:
    """统一入口：自动识别 Excel 类型并解析。
    
    Returns: (records, excel_type, errors)
      - excel_type: 'full_template' | 'simple_url_table' | 'unknown'
      - records: 完整模板返回 dict list（含所有列）；简单表返回 dict list（仅有的列）
      - errors: 错误描述列表
    """
    try:
        raw_df = pd.read_excel(io.BytesIO(file_bytes), dtype=str)
    except Exception as e:
        return [], "unknown", [f"文件读取失败：{e}"]

    raw_df.columns = [str(c).strip() for c in raw_df.columns]
    excel_type = detect_excel_type(raw_df)

    if excel_type == "full_template":
        # 走原有完整模板逻辑（只做基础列映射，由调用方再走 enrich_records）
        from services.excel_importer import parse_excel, validate_required_columns
        df_mapped, errors = parse_excel(file_bytes)
        if df_mapped is None:
            return [], "full_template", errors
        records = df_mapped.to_dict(orient="records")
        return records, "full_template", errors

    elif excel_type == "simple_url_table":
        records, errors = parse_simple_url_table(raw_df)
        return records, "simple_url_table", errors

    else:
        return [], "unknown", ["无法识别 Excel 格式：既不是完整模板，也未找到链接列。请检查表头。"]
