"""官方来源巡检页面 V2（修复版）
修复：
1. StreamlitDuplicateElementKey：所有 widget key 加入 section_key 前缀
2. Nemo 显示问题：docs_pending 进入本期有效候选（待确认）
3. 多 Tab 同一 item 的 checkbox 状态共享（以 stable_item_id 为准）
4. 调试信息：诊断区展示每条结果的 bucket 分配情况
"""
import sys
import os
import hashlib
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import streamlit as st
from datetime import date, timedelta, datetime, timezone

from services.official_source_monitor import run_official_monitor, load_monitoring_config
from services.official_monitor_importer import filter_valid_results, item_to_record, FilterResult
from services.monitor_run_store import save_run, get_runs
from services.data_service import batch_insert

st.set_page_config(page_title="官方来源巡检", layout="wide")
st.title("官方来源巡检")
st.caption("官网 + GitHub 主动巡检 · 主结果只展示时间窗口内有效更新 + 高价值待确认")

_CAT_OPTIONS = ["待评估", "产品与功能", "生态与集成", "市场与运营"]
_IMPORTANCE_OPTIONS = ["high", "medium", "low"]


def _stable_id(item) -> str:
    """以 source_url 计算稳定的 item ID（10位 md5 hex）。"""
    url = getattr(item, "source_url", "") or ""
    return hashlib.md5(url.encode()).hexdigest()[:10]


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


# ── 侧边栏 ────────────────────────────────────────────────────
with st.sidebar:
    st.header("巡检设置")

    try:
        config = load_monitoring_config()
        competitor_options = list(config.keys())
    except Exception as e:
        st.error(f"配置加载失败: {e}")
        competitor_options = ["Tavily"]

    competitor = st.selectbox("竞品", competitor_options, help="Exa / Brave 即将支持")

    today = date.today()
    col1, col2 = st.columns(2)
    with col1:
        start_date = st.date_input("开始日期", value=today - timedelta(days=14))
    with col2:
        end_date = st.date_input("结束日期", value=today)

    st.subheader("来源")
    src_all = st.checkbox("全部", value=True)
    src_web = st.checkbox("官网", value=False, disabled=src_all)
    src_gh  = st.checkbox("GitHub", value=False, disabled=src_all)

    enable_querit = st.checkbox("Querit 补充发现", value=False,
                                help="默认关闭；开启后将调用 Querit API 补充线索")

    run_btn = st.button("开始巡检", type="primary", use_container_width=True,
                        disabled=st.session_state.get("monitor_running", False))

# 构造 source_types
if src_all:
    source_types = ["all"]
else:
    source_types = []
    if src_web: source_types.extend(["blog", "docs", "integrations"])
    if src_gh:  source_types.append("github")
if not source_types:
    source_types = ["all"]

# ── 执行巡检 ──────────────────────────────────────────────────
if run_btn:
    st.session_state["monitor_running"] = True
    window_start = start_date.isoformat()
    window_end   = end_date.isoformat()
    started_at   = _now_iso()

    with st.status("正在巡检...", expanded=True) as status_box:
        st.write("读取配置并开始巡检...")
        try:
            result = run_official_monitor(
                competitor=competitor,
                window_start=window_start,
                window_end=window_end,
                source_types=source_types,
                enable_querit_supplement=enable_querit,
            )
            st.write("结果过滤整理...")
            fr: FilterResult = filter_valid_results(
                result.website_results,
                result.github_results,
                window_start=window_start,
                window_end=window_end,
            )
        except Exception as e:
            status_box.update(label="巡检失败", state="error")
            st.error(f"巡检失败: {e}")
            st.session_state["monitor_running"] = False
            st.stop()
        status_box.update(label="巡检完成", state="complete")

    # 保存批次历史
    try:
        save_run({
            "competitor":   competitor,
            "window_start": window_start,
            "window_end":   window_end,
            "source_types": ",".join(source_types),
            "status":       "completed",
            "blog_count":   len(fr.blog_valid),
            "docs_count":   len(fr.docs_valid) + len(fr.docs_pending),
            "github_count": len(fr.github_valid),
            "querit_count": len(result.querit_supplement_results),
            "total_valid":  len(fr.blog_valid) + len(fr.docs_valid) + len(fr.docs_pending) + len(fr.github_valid),
            "error_count":  len(result.errors),
            "started_at":   started_at,
            "completed_at": result.completed_at,
        })
    except Exception:
        pass

    # 清除上轮 checkbox 状态
    st.session_state["checked_items"] = {}
    st.session_state["item_edits"] = {}

    st.session_state["monitor_result"] = result
    st.session_state["monitor_fr"] = fr
    st.session_state["monitor_running"] = False


# ── 历史记录函数 ──────────────────────────────────────────────
def _show_history():
    with st.expander("最近巡检历史", expanded=False):
        try:
            runs = get_runs(limit=10)
        except Exception:
            runs = []
        if not runs:
            st.caption("暂无巡检记录")
            return
        import pandas as pd
        rows = []
        for r in runs:
            rows.append({
                "ID": r.get("id", ""),
                "竞品": r.get("competitor", ""),
                "时间窗口": f"{r.get('window_start','')} ~ {r.get('window_end','')}",
                "来源": r.get("source_types", ""),
                "有效更新": r.get("total_valid", 0),
                "Blog": r.get("blog_count", 0),
                "Docs": r.get("docs_count", 0),
                "GitHub": r.get("github_count", 0),
                "状态": r.get("status", ""),
                "开始时间": r.get("started_at", "")[:16],
            })
        st.dataframe(pd.DataFrame(rows), use_container_width=True)


if "monitor_result" not in st.session_state:
    st.info("请在左侧配置参数，点击「开始巡检」运行。")
    _show_history()
    st.stop()

result = st.session_state["monitor_result"]
fr: FilterResult = st.session_state["monitor_fr"]

# ── 初始化人工确认状态 ────────────────────────────────────────
if "checked_items" not in st.session_state:
    st.session_state["checked_items"] = {}
if "item_edits" not in st.session_state:
    st.session_state["item_edits"] = {}


# ── 顶部统计卡片 ──────────────────────────────────────────────
# final_github_events = github_valid (已包含 release 合并后的最终事件)
all_confirmed = fr.blog_valid + fr.docs_valid + fr.github_valid
all_candidates = all_confirmed + fr.docs_pending
total_candidate_count = len(all_candidates)

c1, c2, c3, c4, c5, c6, c7, c8 = st.columns(8)
c1.metric("有效候选总数", total_candidate_count)
c2.metric("Blog 更新", len(fr.blog_valid))
c3.metric("Docs 确认更新", len(fr.docs_valid))
c4.metric("Docs 待确认", len(fr.docs_pending))
c5.metric("GitHub 更新事件", len(fr.github_valid))   # final_github_events（含 release）
c6.metric("Querit 补充", len(result.querit_supplement_results))
c7.metric("错误", len(result.errors))
# 诊断用：原始 GitHub 动态数量
raw_gh_count = result.source_stats.get("github_commits", {}).get("found", 0)
c8.metric("原始 GitHub 记录", raw_gh_count, help="不计入有效候选，仅供参考")

st.divider()


# ── widget 渲染（section_key 确保唯一） ───────────────────────

def _render_item_card(item, section_key: str, is_pending: bool = False):
    """渲染单条结果卡片。

    section_key：视图上下文前缀（all/blog/docs/github/pending/querit）
    is_pending：是否为待确认类型（用于标注）
    widget key 格式：{prefix}_{section_key}_{stable_id}
    业务选中状态存入 session_state["checked_items"][stable_id]（跨 Tab 共享）
    """
    sid = _stable_id(item)
    # widget key 含 section_key 以保证唯一性
    w = lambda prefix: f"{prefix}_{section_key}_{sid}"

    date_display = (item.published_at or item.updated_at or item.update_date or "—")[:10]
    channel_label = {
        "website_blog": "Blog",
        "website_docs": "Docs",
        "website_integration": "Integration",
        "github_commit_group": "GitHub Commits",
        "github_release": "GitHub Release",
    }.get(item.source_channel or "", item.source_channel or "?")

    title_str = item.update_title or "（无标题）"
    pending_badge = " ⚠ 待确认" if is_pending else ""

    with st.expander(
        f"[{channel_label}]{pending_badge}  {title_str[:80]}  —  {date_display}",
        expanded=False,
    ):
        col_a, col_b = st.columns([3, 1])
        with col_a:
            st.markdown(f"**标题：** {title_str}")
            st.markdown(f"**日期：** {date_display}")
            st.markdown(f"**来源：** {channel_label}")
            st.markdown(
                f"**update_status：** `{item.update_status or '—'}`  "
                f"|  **discovery_method：** `{item.discovery_method or '—'}`"
            )
            if is_pending:
                st.info("首次系统发现，无历史快照可对比，建议人工确认后写入看板。")
            if item.source_url:
                st.markdown(f"**链接：** [{item.source_url}]({item.source_url})")
            if item.summary:
                st.markdown(f"**摘要：** {item.summary[:300]}")
            if item.key_points:
                st.markdown("**关键变化：**")
                for kp in item.key_points[:5]:
                    st.markdown(f"- {kp}")
            # GitHub 额外
            if item.source_channel == "github_commit_group" and item.evidence_urls:
                st.markdown(f"**Commit 数：** {len(item.evidence_urls)}")
                with st.expander("原始 Commit 链接", expanded=False):
                    for u in item.evidence_urls[:10]:
                        st.markdown(f"- [{u}]({u})")
            # Docs 额外
            if item.source_channel in ("website_docs", "website_integration"):
                if item.updated_at:
                    st.markdown(f"**lastmod (updated_at)：** {item.updated_at}")
                if getattr(item, "docs_page_role", ""):
                    st.markdown(f"**页面角色：** `{item.docs_page_role}`")
        with col_b:
            st.markdown(f"**分类：** {item.category or '—'}")
            st.markdown(f"**重要程度：** {item.importance or '—'}")
            if item.querit_relevance:
                st.markdown(f"**Querit 参考：** {item.querit_relevance}")

        st.markdown("---")
        # checkbox：value 从共享状态读取，key 含 section_key
        cur_checked = st.session_state["checked_items"].get(sid, False)
        new_checked = st.checkbox(
            "加入待审核区",
            key=w("chk"),
            value=cur_checked,
        )
        st.session_state["checked_items"][sid] = new_checked

        if new_checked:
            edits = st.session_state["item_edits"].get(sid, {})
            e_summary = st.text_area(
                "编辑摘要", value=edits.get("summary", item.summary or ""),
                key=w("sum"), height=80,
            )
            e_cat = st.selectbox(
                "分类", _CAT_OPTIONS,
                index=_CAT_OPTIONS.index(edits.get("category", "待评估"))
                if edits.get("category", "待评估") in _CAT_OPTIONS else 0,
                key=w("cat"),
            )
            e_imp = st.selectbox(
                "重要程度", _IMPORTANCE_OPTIONS,
                index=_IMPORTANCE_OPTIONS.index(
                    edits.get("priority", item.importance or "medium")
                ) if (edits.get("priority") or item.importance or "medium") in _IMPORTANCE_OPTIONS else 1,
                key=w("imp"),
            )
            e_querit = st.text_area(
                "对 Querit 的参考价值",
                value=edits.get("querit_status", item.querit_relevance or ""),
                key=w("qrel"), height=60,
            )
            st.session_state["item_edits"][sid] = {
                "summary":      e_summary,
                "category":     e_cat,
                "priority":     e_imp,
                "querit_status": e_querit,
            }

    return sid, st.session_state["checked_items"].get(sid, False)


# ── 主 Tabs ────────────────────────────────────────────────────
tabs = st.tabs([
    f"本期有效候选 ({total_candidate_count})",
    f"Blog ({len(fr.blog_valid)})",
    f"Docs & Integration ({len(fr.docs_valid)})",
    f"GitHub ({len(fr.github_valid)})",
    f"Docs 待确认 ({len(fr.docs_pending)})",
    f"Querit 补充 ({len(result.querit_supplement_results)})",
    "诊断信息",
])

# Tab 0：本期有效候选（确认 + 待确认）
with tabs[0]:
    if not all_candidates:
        st.info("本次巡检未发现窗口内有效更新或待确认条目。")
    else:
        if fr.blog_valid or fr.docs_valid or fr.github_valid:
            st.markdown("#### 已确认更新")
            for i, item in enumerate(fr.blog_valid + fr.docs_valid + fr.github_valid):
                _render_item_card(item, "all", is_pending=False)
        if fr.docs_pending:
            st.markdown("#### 待确认（高价值首次发现）")
            for i, item in enumerate(fr.docs_pending):
                _render_item_card(item, "all_pend", is_pending=True)

# Tab 1：Blog
with tabs[1]:
    if not fr.blog_valid:
        st.info("本次巡检未发现窗口内 Blog 更新。")
    for i, item in enumerate(fr.blog_valid):
        _render_item_card(item, "blog")

# Tab 2：Docs & Integration
with tabs[2]:
    if not fr.docs_valid:
        st.info("本次巡检未发现 Docs 确认更新（首次运行无历史快照，请查看「Docs 待确认」标签）。")
    for i, item in enumerate(fr.docs_valid):
        _render_item_card(item, "docs")

# Tab 3：GitHub
with tabs[3]:
    if not fr.github_valid:
        st.info("本次巡检未发现窗口内 GitHub 更新。")
    else:
        # 显示 synthesis_method 标注
        synthesis_methods = {getattr(i, "synthesis_method", "") for i in fr.github_valid}
        if "mock_llm_synthesis" in synthesis_methods:
            st.caption("synthesis_method = mock_llm_synthesis（Mock LLM 合成，可切换 GITHUB_SYNTHESIS_PROVIDER=openai/anthropic）")
        elif "llm_synthesis" in synthesis_methods:
            st.caption("synthesis_method = llm_synthesis")
        else:
            st.caption("synthesis_method = deterministic")

    for i, item in enumerate(fr.github_valid):
        be = getattr(item, "github_business_event", None)
        if be:
            # 展示 GithubBusinessEvent 完整信息
            ev_type = be.event_type or item.source_channel or "—"
            confidence_str = f"{be.confidence:.0%}" if be.confidence else "—"
            date_str = be.event_date[:10] if be.event_date else "—"
            with st.expander(
                f"[{ev_type}]  {be.event_title[:80]}  —  {date_str}  "
                f"(confidence={confidence_str}, evidence={be.evidence_count})",
                expanded=False,
            ):
                col_a, col_b = st.columns([3, 1])
                with col_a:
                    st.markdown(f"**标题：** {be.event_title}")
                    st.markdown(f"**日期：** {date_str}")
                    st.markdown(f"**事件类型：** `{be.event_type}` | **synthesis：** `{be.synthesis_method}`")
                    if be.summary:
                        st.markdown(f"**摘要：** {be.summary}")
                    if be.developer_impact:
                        st.markdown(f"**开发者影响：** {be.developer_impact}")
                    if be.business_relevance:
                        st.markdown(f"**商业参考价值：** {be.business_relevance}")
                    if be.key_changes:
                        st.markdown("**关键变化：**")
                        for kc in be.key_changes[:5]:
                            st.markdown(f"- {kc}")
                    if be.repositories:
                        st.markdown(f"**涉及仓库：** {', '.join(be.repositories)}")
                    st.markdown(f"**证据（{be.evidence_count} 条）：**")
                    for u in be.evidence_urls[:8]:
                        st.markdown(f"- [{u}]({u})")
                with col_b:
                    st.markdown(f"**分类：** {be.category or '—'}")
                    st.markdown(f"**重要程度：** {be.importance}")
                    st.markdown(f"**置信度：** {confidence_str}")
                    st.markdown(f"**来源方式：** `{be.synthesis_method}`")

                st.markdown("---")
                sid = _stable_id(item)
                w = lambda prefix: f"{prefix}_github_{sid}"
                cur_checked = st.session_state["checked_items"].get(sid, False)
                new_checked = st.checkbox("加入待审核区", key=w("chk"), value=cur_checked)
                st.session_state["checked_items"][sid] = new_checked
                if new_checked:
                    edits = st.session_state["item_edits"].get(sid, {})
                    e_summary = st.text_area("编辑摘要", value=edits.get("summary", be.summary or ""),
                                             key=w("sum"), height=80)
                    e_cat = st.selectbox("分类", _CAT_OPTIONS,
                                         index=_CAT_OPTIONS.index(edits.get("category", "待评估"))
                                         if edits.get("category", "待评估") in _CAT_OPTIONS else 0,
                                         key=w("cat"))
                    e_imp = st.selectbox("重要程度", _IMPORTANCE_OPTIONS,
                                         index=_IMPORTANCE_OPTIONS.index(edits.get("priority", be.importance or "medium"))
                                         if (edits.get("priority") or be.importance or "medium") in _IMPORTANCE_OPTIONS else 1,
                                         key=w("imp"))
                    st.session_state["item_edits"][sid] = {
                        "summary": e_summary, "category": e_cat, "priority": e_imp,
                    }
        else:
            _render_item_card(item, "github")

# Tab 4：Docs 待确认
with tabs[4]:
    if not fr.docs_pending:
        st.info("无高价值 Docs 待确认条目。")
    else:
        st.caption("以下页面为首次系统发现或无历史快照对比，需人工判断是否属于有效竞品更新。")
    for i, item in enumerate(fr.docs_pending):
        _render_item_card(item, "pend", is_pending=True)

# Tab 5：Querit 补充
with tabs[5]:
    if not result.querit_supplement_results:
        st.info("Querit 补充已关闭或无额外线索。" if not enable_querit else "未发现补充线索。")
    for i, item in enumerate(result.querit_supplement_results):
        _render_item_card(item, "querit")

# Tab 6：诊断信息
with tabs[6]:
    if result.errors:
        st.warning(f"巡检过程中发生 {len(result.errors)} 个错误：")
        for err in result.errors:
            st.error(f"[{err.get('source_type','?')}] {err.get('error','')[:200]}")
    else:
        st.success("巡检无错误")

    if result.source_stats:
        st.subheader("来源统计")
        import pandas as pd
        rows = []
        for src, stat in result.source_stats.items():
            if src in ("brave_search_filter", "blog_funnel", "docs_funnel"):
                continue  # Brave 专属字段单独展示
            rows.append({
                "来源": src,
                "发现总数": stat.get("found", 0),
                "窗口内": stat.get("in_window", 0),
                "聚合事件": stat.get("aggregated_events", "—"),
                "docs_status": stat.get("docs_status", "—"),
                "github_status": stat.get("github_status", "—"),
            })
        st.dataframe(pd.DataFrame(rows), use_container_width=True)

        # ── Brave 专属漏斗展示 ────────────────────────────────────
        blog_funnel = result.source_stats.get("blog_funnel")
        brave_filter = result.source_stats.get("brave_search_filter")
        docs_status = result.source_stats.get("docs", {}).get("docs_status", "")
        github_status = result.source_stats.get("github_commits", {}).get("github_status", "")
        if blog_funnel or brave_filter:
            st.subheader("Brave Search 诊断漏斗")
            if blog_funnel:
                discovered = blog_funnel.get("blog_discovered", 0)
                search_rel = blog_funnel.get("blog_search_related", 0)
                non_search = blog_funnel.get("blog_non_search_filtered", 0)
                in_win = blog_funnel.get("blog_in_window", 0)
                out_win = blog_funnel.get("blog_outside_window", 0)
                inv_date = blog_funnel.get("blog_invalid_date", 0)
                funnel_text = (
                    f"Blog discovered:      {discovered}\n"
                    f"├─ Non-search filtered: {non_search}\n"
                    f"└─ Search-related:     {search_rel}\n"
                    f"    ├─ In window:      {in_win}\n"
                    f"    ├─ Outside window: {out_win}\n"
                    f"    └─ Invalid date:   {inv_date}"
                )
                st.code(funnel_text, language=None)
                if discovered == search_rel + non_search and search_rel == in_win + out_win + inv_date:
                    st.success("漏斗数量校验通过（各字段加总一致）")
                else:
                    st.warning(f"漏斗数量不一致：{search_rel} + {non_search} ≠ {discovered} 或 {in_win}+{out_win}+{inv_date} ≠ {search_rel}")

            # Docs 漏斗
            docs_funnel = result.source_stats.get("docs_funnel")
            if docs_funnel:
                df_disc = docs_funnel.get("docs_discovered", 0)
                df_rel = docs_funnel.get("docs_search_related", 0)
                df_non = docs_funnel.get("docs_non_search_filtered", 0)
                df_in = docs_funnel.get("docs_in_window", 0)
                df_out = docs_funnel.get("docs_outside_window", 0)
                df_unk = docs_funnel.get("docs_date_unknown", 0)
                df_dsrc = docs_funnel.get("docs_date_source", "—")
                docs_funnel_text = (
                    f"Docs discovered:      {df_disc}\n"
                    f"├─ Non-search filtered: {df_non}\n"
                    f"└─ Search-related:     {df_rel}\n"
                    f"    ├─ In window:      {df_in}  (date_source={df_dsrc})\n"
                    f"    ├─ Outside window: {df_out}\n"
                    f"    └─ Date unknown:   {df_unk}"
                )
                st.code(docs_funnel_text, language=None)
            if docs_status:
                _docs_color = {"ok": "success", "blocked_403": "error",
                               "unavailable": "warning", "no_pages_found": "info"}.get(docs_status, "info")
                getattr(st, _docs_color)(f"Docs 状态: `{docs_status}`")
            if github_status:
                if github_status == "success_no_updates":
                    st.info("GitHub 状态: `success_no_updates` — 相关 repo 已正常检查，时间窗口内无 commit/release")
                elif github_status == "ok":
                    st.success("GitHub 状态: `ok`")
                elif github_status == "error":
                    st.error("GitHub 状态: `error` — 详见上方错误信息")

    # Nemo 调试输出
    st.subheader("结果分桶调试（Nemo 诊断）")
    nemo_dbg = [
        d for d in fr.debug_items
        if "nemo" in (d.source_url or "").lower() or "nemo" in (d.title or "").lower()
    ]
    if nemo_dbg:
        for d in nemo_dbg:
            st.json({
                "title": d.title,
                "source_url": d.source_url,
                "source_channel": d.source_channel,
                "docs_page_role": d.docs_page_role,
                "update_status": d.update_status,
                "published_at": d.published_at,
                "updated_at": d.updated_at,
                "within_window": d.within_window,
                "is_generic_page": d.is_generic_page,
                "bucket": d.bucket,
                "drop_reason": d.drop_reason,
            })
    else:
        st.info("未在此次巡检结果中找到 Nemo 相关条目。")

    # 原始 GitHub 动态（诊断/审计区）
    gh_diag = getattr(result, "github_diagnostic_results", [])
    if gh_diag:
        with st.expander(f"原始 GitHub 动态（低相关性/维护类 {len(gh_diag)} 条）", expanded=False):
            st.caption("以下事件已被相关性过滤器归为 maintenance / internal_only，不计入有效候选数量。仅供审计。")
            for item in gh_diag:
                rel = getattr(item, "github_relevance", "—")
                reason = getattr(item, "github_relevance_reason", "")
                st.markdown(
                    f"- `{rel}` | **{item.update_title or '—'}** — {item.update_date or '—'}"
                )
                if item.source_url:
                    st.caption(f"  {item.source_url}  |  reason: {reason[:80]}")

    # 全量诊断折叠区
    outside_all = fr.outside_window + fr.metadata_only + fr.generic_page
    if outside_all:
        with st.expander(f"窗口外 / metadata_only / 通用低价值（{len(outside_all)} 条）", expanded=False):
            for item in outside_all:
                date_str = (item.published_at or item.updated_at or item.update_date or "—")[:10]
                st.markdown(
                    f"- `{item.update_status}` | `{item.source_channel}` "
                    f"| **{item.update_title or '—'}** — {date_str}"
                )
                if item.source_url:
                    st.caption(item.source_url)

    if fr.debug_items:
        with st.expander(f"全量分桶明细（{len(fr.debug_items)} 条）", expanded=False):
            import pandas as pd
            rows = []
            for d in fr.debug_items:
                rows.append({
                    "title": d.title[:50],
                    "channel": d.source_channel,
                    "role": d.docs_page_role,
                    "status": d.update_status,
                    "in_window": d.within_window,
                    "generic": d.is_generic_page,
                    "bucket": d.bucket,
                    "drop_reason": d.drop_reason[:60] if d.drop_reason else "",
                })
            st.dataframe(pd.DataFrame(rows), use_container_width=True)

    st.caption(f"巡检完成: {result.completed_at}")

# ── 加入待审核区 ──────────────────────────────────────────────
st.divider()
checked_sids = [sid for sid, v in st.session_state.get("checked_items", {}).items() if v]
st.markdown(f"**已勾选 {len(checked_sids)} 条** 待加入审核区")

if st.button("加入待审核区", disabled=len(checked_sids) == 0, type="primary"):
    all_candidate_items = (
        fr.blog_valid + fr.docs_valid + fr.github_valid +
        fr.docs_pending + result.querit_supplement_results
    )
    records_to_insert = []
    for item in all_candidate_items:
        sid = _stable_id(item)
        if sid in checked_sids:
            edits = st.session_state.get("item_edits", {}).get(sid, {})
            records_to_insert.append(item_to_record(item, user_edits=edits))

    if records_to_insert:
        batch_result = batch_insert(records_to_insert)
        st.success(
            f"写入完成：成功 {batch_result['success']} 条，"
            f"重复跳过 {batch_result['duplicate']} 条，"
            f"错误 {batch_result['error']} 条"
        )
        for err in batch_result.get("errors", [])[:5]:
            st.warning(f"写入错误: {err}")
    else:
        st.warning("未找到已勾选条目，请在结果区勾选后再提交。")

# ── 历史批次 ──────────────────────────────────────────────────
st.divider()
_show_history()
