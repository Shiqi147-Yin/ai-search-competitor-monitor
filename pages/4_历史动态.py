"""历史动态页面"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import streamlit as st
import pandas as pd
from datetime import date, timedelta
import database
from services.data_service import get_history, export_to_excel
from config import COMPETITORS, CATEGORIES, SOURCE_PLATFORMS, QUERIT_STATUS_OPTIONS, PRIORITY_OPTIONS

st.set_page_config(page_title="历史动态", page_icon="📚", layout="wide")
st.title("📚 历史动态")

# ── 侧边栏筛选 ────────────────────────────────────────────────
with st.sidebar:
    st.header("筛选条件")

    date_start = st.date_input("发布时间（起）", value=date.today() - timedelta(days=90))
    date_end = st.date_input("发布时间（止）", value=date.today())

    all_weeks = database.get_all_week_ids()
    sel_weeks = st.multiselect("周次", all_weeks, default=[])

    sel_competitors = st.multiselect("竞品", COMPETITORS, default=[])
    sel_categories = st.multiselect("分类", ["产品与功能", "生态与集成", "市场与运营"], default=[])
    sel_platforms = st.multiselect("信息平台", SOURCE_PLATFORMS, default=[])
    sel_querit = st.multiselect("Querit 状态", QUERIT_STATUS_OPTIONS, default=[])
    keyword = st.text_input("关键词（标题/摘要）", "")

# ── 构造过滤参数 ──────────────────────────────────────────────
filters: dict = {
    "publish_date_start": date_start.isoformat(),
    "publish_date_end": date_end.isoformat(),
}
if sel_weeks:
    filters["week_id"] = sel_weeks
if sel_competitors:
    filters["competitor"] = sel_competitors
if sel_categories:
    filters["category"] = sel_categories
if sel_platforms:
    filters["source_platform"] = sel_platforms
if sel_querit:
    filters["querit_status"] = sel_querit
if keyword.strip():
    filters["keyword"] = keyword.strip()

records = get_history(filters)
st.caption(f"共 {len(records)} 条历史数据（筛选后）")

if not records:
    st.info("没有符合条件的历史数据。")
    st.stop()

# ── 展示表格 ──────────────────────────────────────────────────
df = pd.DataFrame(records)

DISPLAY_COLUMNS = {
    "publish_date": "发布时间",
    "competitor": "竞品",
    "category": "分类",
    "title": "标题",
    "summary": "摘要",
    "source_platform": "平台",
    "querit_status": "Querit状态",
    "priority": "优先级",
    "week_id": "周次",
    "source_url": "原始链接",
}

show_cols = [c for c in DISPLAY_COLUMNS if c in df.columns]
df_display = df[show_cols].copy()
df_display.columns = [DISPLAY_COLUMNS[c] for c in show_cols]

column_config = {}
if "原始链接" in df_display.columns:
    column_config["原始链接"] = st.column_config.LinkColumn(
        "原始链接", display_text="查看原文"
    )

st.dataframe(
    df_display,
    use_container_width=True,
    height=500,
    column_config=column_config,
)

# ── 导出 Excel ────────────────────────────────────────────────
st.divider()
excel_bytes = export_to_excel(records)
st.download_button(
    label="📥 导出当前筛选结果为 Excel",
    data=excel_bytes,
    file_name=f"competitor_history_export.xlsx",
    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
)
