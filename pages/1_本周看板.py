"""本周看板页面"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import streamlit as st
from services.data_service import get_current_week_id, get_weekly_dashboard
from config import COMPETITORS, CATEGORIES, PRIORITY_OPTIONS, QUERIT_STATUS_OPTIONS

st.set_page_config(page_title="本周看板", page_icon="📊", layout="wide")

# ── 全局样式 ──────────────────────────────────────────────────
st.markdown("""
<style>
.update-card{border:1px solid #e0e0e0;border-radius:8px;padding:12px 16px;margin-bottom:10px;background:#fafafa;}
.badge-high{background:#c0392b;color:#fff;border-radius:4px;padding:2px 8px;font-size:12px;}
.badge-medium{background:#e67e22;color:#fff;border-radius:4px;padding:2px 8px;font-size:12px;}
.badge-low{background:#27ae60;color:#fff;border-radius:4px;padding:2px 8px;font-size:12px;}
.qs-badge{background:#2c3e50;color:#fff;border-radius:4px;padding:2px 8px;font-size:12px;}
</style>
""", unsafe_allow_html=True)

st.title("📊 本周看板")
current_week = get_current_week_id()
st.caption(f"当前周次：{current_week}")

# ── 侧边栏筛选 ────────────────────────────────────────────────
with st.sidebar:
    st.header("筛选条件")
    sel_competitors = st.multiselect("竞品", COMPETITORS, default=[])
    sel_categories = st.multiselect("分类", ["产品与功能", "生态与集成", "市场与运营"], default=[])
    sel_priorities = st.multiselect("优先级", PRIORITY_OPTIONS, default=[])
    sel_querit = st.multiselect("Querit 状态", QUERIT_STATUS_OPTIONS, default=[])

# ── 查询数据 ──────────────────────────────────────────────────
extra: dict = {}
if sel_competitors:
    extra["competitor"] = sel_competitors
if sel_categories:
    extra["category"] = sel_categories
if sel_priorities:
    extra["priority"] = sel_priorities
if sel_querit:
    extra["querit_status"] = sel_querit

records = get_weekly_dashboard(current_week, extra)

# ── 顶部指标 ──────────────────────────────────────────────────
total = len(records)
cat_product = sum(1 for r in records if r.get("category") == "产品与功能")
cat_eco = sum(1 for r in records if r.get("category") == "生态与集成")
cat_market = sum(1 for r in records if r.get("category") == "市场与运营")
high_prio = sum(1 for r in records if r.get("priority") == "高")
querit_covered = sum(1 for r in records if r.get("querit_status") in ("已覆盖", "推进中"))
last_updated = max((r.get("updated_at") or "") for r in records) if records else "—"
if last_updated and len(last_updated) > 19:
    last_updated = last_updated[:19].replace("T", " ")

m1, m2, m3, m4, m5, m6, m7 = st.columns(7)
m1.metric("本周新增动态", total)
m2.metric("产品与功能", cat_product)
m3.metric("生态与集成", cat_eco)
m4.metric("市场与运营", cat_market)
m5.metric("高优先级", high_prio)
m6.metric("Querit已覆盖/推进中", querit_covered)
m7.metric("最后更新时间", last_updated)

st.divider()

if not records:
    st.info("本周暂无已确认动态。请先在「数据导入」上传数据，并在「待审核区」确认后显示。")
    st.stop()

# ── badge 辅助函数 ────────────────────────────────────────────
PRIORITY_BADGE = {"高": "badge-high", "中": "badge-medium", "低": "badge-low"}
QS_COLOR = {
    "已覆盖": "#1a6b3c", "部分覆盖": "#2471a3", "推进中": "#7d3c98",
    "待评估": "#797d7f", "暂无": "#b2bec3", "不跟进": "#636e72",
}

def priority_badge(p: str) -> str:
    cls = PRIORITY_BADGE.get(p, "badge-low")
    return f'<span class="{cls}">{p}</span>'

def qs_badge(qs: str) -> str:
    color = QS_COLOR.get(qs, "#636e72")
    txt_color = "#fff" if qs != "暂无" else "#333"
    return f'<span style="background:{color};color:{txt_color};border-radius:4px;padding:2px 8px;font-size:12px;">{qs}</span>'

def render_card(r: dict):
    url = r.get("source_url") or ""
    link_html = f'<a href="{url}" target="_blank" rel="noopener">查看原文</a>' if url else "—"
    st.markdown(f"""
<div class="update-card">
  <b>{r.get('title', '')}</b>
  &nbsp;&nbsp;{priority_badge(r.get('priority',''))}
  &nbsp;{qs_badge(r.get('querit_status',''))}
  <br/>
  <small style="color:#666;">
    {r.get('competitor','—')} &nbsp;|&nbsp; {r.get('publish_date','—')} &nbsp;|&nbsp; {link_html}
  </small>
  <p style="margin:6px 0 0;font-size:14px;color:#333;">{r.get('summary','') or ''}</p>
</div>
""", unsafe_allow_html=True)

# ── 分 tab 展示 ───────────────────────────────────────────────
tab1, tab2, tab3, tab4 = st.tabs(["产品与功能", "生态与集成", "市场与运营", "其他"])
category_map = {
    "产品与功能": tab1,
    "生态与集成": tab2,
    "市场与运营": tab3,
}
others = []

for r in records:
    cat = r.get("category", "")
    if cat in category_map:
        with category_map[cat]:
            render_card(r)
    else:
        others.append(r)

with tab4:
    if others:
        for r in others:
            render_card(r)
    else:
        st.caption("暂无其他分类数据")
