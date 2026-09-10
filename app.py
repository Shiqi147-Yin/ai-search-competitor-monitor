"""Streamlit 多页面应用主入口"""
import streamlit as st
import sys
from pathlib import Path

# 确保项目根目录在 sys.path 中
ROOT = Path(__file__).parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# ── 最先加载 .env，确保所有模块拿到正确的环境变量 ──────────────
from env_loader import load_env
load_env()

import database
from services.data_service import get_current_week_id

# ── 初始化数据库 + 全量 migration（含新鲜度字段）──────────────
database.init_db()
database.run_migrations()

# ── 页面配置 ──────────────────────────────────────────────────
st.set_page_config(
    page_title="AI Search API 竞品看板",
    page_icon="🔍",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── 全局 CSS ──────────────────────────────────────────────────
st.markdown(
    """
    <style>
    /* 侧边栏标题 */
    [data-testid="stSidebarNav"] { font-size: 14px; }
    /* 卡片容器 */
    .update-card {
        border: 1px solid #e0e0e0;
        border-radius: 8px;
        padding: 12px 16px;
        margin-bottom: 10px;
        background: #fafafa;
    }
    /* 优先级 badge */
    .badge-high   { background:#c0392b; color:#fff; border-radius:4px; padding:2px 8px; font-size:12px; }
    .badge-medium { background:#e67e22; color:#fff; border-radius:4px; padding:2px 8px; font-size:12px; }
    .badge-low    { background:#27ae60; color:#fff; border-radius:4px; padding:2px 8px; font-size:12px; }
    /* Querit 状态 badge */
    .qs-covered   { background:#1a6b3c; color:#fff; border-radius:4px; padding:2px 8px; font-size:12px; }
    .qs-partial   { background:#2471a3; color:#fff; border-radius:4px; padding:2px 8px; font-size:12px; }
    .qs-inprog    { background:#7d3c98; color:#fff; border-radius:4px; padding:2px 8px; font-size:12px; }
    .qs-pending   { background:#797d7f; color:#fff; border-radius:4px; padding:2px 8px; font-size:12px; }
    .qs-none      { background:#b2bec3; color:#333; border-radius:4px; padding:2px 8px; font-size:12px; }
    </style>
    """,
    unsafe_allow_html=True,
)

# ── 首页内容 ──────────────────────────────────────────────────
st.title("🔍 AI Agent Search API 竞品看板")
st.markdown(
    f"""
当前周次：**{get_current_week_id()}**

---

### 系统简介

本看板用于长期跟踪 **Tavily、Exa、Brave** 等 AI Agent Search API 竞品动态，
并将竞品信息与 **Querit** 当前进展放在同一套看板中进行对照分析。

**使用流程：**

1. **数据导入** — 下载 Excel 模板，填写竞品动态后上传
2. **待审核区** — 审阅导入数据，补充分析字段后确认
3. **本周看板** — 查看本周已确认动态及关键指标
4. **历史动态** — 全量历史数据检索与导出

---
""",
    unsafe_allow_html=False,
)

col1, col2, col3 = st.columns(3)
with col1:
    st.info("**数据导入**\n\n上传 Excel 文件，自动校验并写入数据库")
with col2:
    st.info("**待审核区**\n\n审核并补充分析，标记确认或忽略")
with col3:
    st.info("**历史动态**\n\n多条件筛选，支持导出 Excel")
