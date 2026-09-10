"""Excel 解析服务：读取、校验、字段补全"""
import io
from datetime import datetime, timezone

import pandas as pd

from config import EXCEL_COLUMN_MAP, EXCEL_REQUIRED_COLUMNS, REQUIRED_FIELDS
from services.data_service import get_current_week_id


def validate_required_columns(df: pd.DataFrame) -> list[str]:
    """检查 DataFrame 是否包含全部必须列名。返回缺失列名列表。"""
    missing = [col for col in EXCEL_REQUIRED_COLUMNS if col not in df.columns]
    return missing


def parse_excel(file_bytes: bytes) -> tuple[pd.DataFrame | None, list[str]]:
    """解析 Excel 字节流。

    Returns
    -------
    (df, errors)
        df     — 映射后的 DataFrame（含原始列名重命名），出错时为 None
        errors — 中文错误描述列表
    """
    errors: list[str] = []

    try:
        raw_df = pd.read_excel(io.BytesIO(file_bytes), dtype=str)
    except Exception as e:
        return None, [f"文件读取失败：{e}"]

    # 去除列名首尾空格
    raw_df.columns = [str(c).strip() for c in raw_df.columns]

    # 检查必须列
    missing_cols = validate_required_columns(raw_df)
    if missing_cols:
        return None, [f"缺少必须列：{', '.join(missing_cols)}，请使用标准模板"]

    # 重命名为数据库字段名
    df = raw_df.rename(columns=EXCEL_COLUMN_MAP)

    # 删除全空行
    df = df.dropna(how="all").reset_index(drop=True)

    # 校验必填字段（title, source_url）
    for field_name, display_name in [("title", "动态标题"), ("source_url", "原始链接")]:
        blank_rows = df[df[field_name].isna() | (df[field_name].str.strip() == "")].index
        for idx in blank_rows:
            errors.append(f"第 {idx + 2} 行：\u201c{display_name}\u201d不能为空")

    # 校验日期格式
    for idx, row in df.iterrows():
        date_val = row.get("publish_date")
        if pd.notna(date_val) and str(date_val).strip():
            try:
                pd.to_datetime(str(date_val).strip())
            except Exception:
                errors.append(f"第 {idx + 2} 行：发布时间格式有误（\u201c{date_val}\u201d），请使用 YYYY-MM-DD 格式")

    return df, errors


def enrich_records(df: pd.DataFrame) -> pd.DataFrame:
    """自动补充系统字段：collected_at、source_mode、week_id、review_status、category、querit_status、priority。"""
    now_iso = datetime.now(timezone.utc).isoformat()
    week_id = get_current_week_id()

    df = df.copy()
    df["collected_at"] = now_iso
    df["source_mode"] = "manual_excel"
    df["week_id"] = week_id
    df["review_status"] = "待审核"

    # 仅对空值补默认
    if "category" not in df.columns or df["category"].isna().all():
        df["category"] = "待评估"
    else:
        df["category"] = df["category"].fillna("待评估")

    if "querit_status" not in df.columns or df["querit_status"].isna().all():
        df["querit_status"] = "待评估"
    else:
        df["querit_status"] = df["querit_status"].fillna("待评估")

    if "priority" not in df.columns or df["priority"].isna().all():
        df["priority"] = "中"
    else:
        df["priority"] = df["priority"].fillna("中")

    df["updated_at"] = now_iso

    # 标准化日期格式
    def _normalize_date(val):
        if pd.isna(val) or str(val).strip() == "":
            return None
        try:
            return pd.to_datetime(str(val).strip()).strftime("%Y-%m-%d")
        except Exception:
            return str(val).strip()

    df["publish_date"] = df["publish_date"].apply(_normalize_date)

    # 清理字符串字段首尾空格
    str_cols = ["title", "source_url", "summary", "competitor",
                "source_platform", "gap_analysis"]
    for col in str_cols:
        if col in df.columns:
            df[col] = df[col].apply(
                lambda x: str(x).strip() if pd.notna(x) and str(x).strip() else None
            )

    return df
