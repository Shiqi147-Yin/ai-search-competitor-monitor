"""待审核区页面 — Phase 4：自动建议直接预填，人工字段优先"""
import sys
import json
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import streamlit as st
from services.data_service import (
    get_pending_review, confirm_record, ignore_record, refetch_and_update,
)
from services.content_analyzer import (
    analyze_record, form_default, form_source_hint,
)
import database
from config import QUERIT_STATUS_OPTIONS, PRIORITY_OPTIONS

st.set_page_config(page_title="待审核区", page_icon="🔎", layout="wide")
st.title("🔎 待审核区")

_FETCH_BADGE = {
    "success":    ("✅ 抓取成功", "#1a6b3c"),
    "partial":    ("⚠️ 部分成功", "#e67e22"),
    "failed":     ("❌ 抓取失败", "#c0392b"),
    "restricted": ("🔒 访问受限", "#7d3c98"),
    "pending":    ("⏳ 待抓取",   "#797d7f"),
}

_ANALYSIS_BADGE = {
    "analyzed": ("🟢 已分析",   "#1a6b3c"),
    "partial":  ("🟡 部分分析", "#e67e22"),
    "failed":   ("🔴 分析失败", "#c0392b"),
    "pending":  ("⚪ 待分析",   "#797d7f"),
}

_CAT_OPTIONS = ["产品与功能", "生态与集成", "市场与运营", "待评估"]

records = get_pending_review()

if not records:
    st.success("待审核区为空，所有数据已处理完毕。")
    st.stop()

st.caption(f"共 {len(records)} 条待审核数据")

# ── 批量重新抓取 ──────────────────────────────────────────────
needs_refetch = [r for r in records
                 if r.get("fetch_status") in ("failed", "partial", "restricted", "pending", None, "")]
if needs_refetch:
    st.info(f"{len(needs_refetch)} 条记录抓取失败或状态待定，可批量重新抓取。")
    if st.button("🔄 重新抓取全部失败记录", key="bulk_refetch"):
        st.session_state["confirm_bulk_refetch"] = True

    if st.session_state.get("confirm_bulk_refetch"):
        st.warning(f"将对 {len(needs_refetch)} 条记录重新抓取，确认继续？")
        col_yes, col_no, _ = st.columns([1, 1, 6])
        with col_yes:
            if st.button("确认执行", key="bulk_refetch_yes", type="primary"):
                st.session_state["confirm_bulk_refetch"] = False
                ok_n, partial_n, fail_n = 0, 0, 0
                prog = st.progress(0)
                for idx, r in enumerate(needs_refetch):
                    url = r.get("source_url") or ""
                    rid = r.get("id")
                    if url and rid:
                        try:
                            res = refetch_and_update(rid, url)
                            if res["status"] == "success":
                                ok_n += 1
                            elif res["status"] in ("partial", "restricted"):
                                partial_n += 1
                            else:
                                fail_n += 1
                        except Exception:
                            fail_n += 1
                    else:
                        fail_n += 1
                    prog.progress((idx + 1) / len(needs_refetch))
                prog.empty()
                st.success(f"批量完成：成功 {ok_n}，部分 {partial_n}，失败 {fail_n}")
                st.rerun()
        with col_no:
            if st.button("取消", key="bulk_refetch_no"):
                st.session_state["confirm_bulk_refetch"] = False
                st.rerun()

st.divider()


# ── 辅助 ─────────────────────────────────────────────────────
def _cat_index(val: str) -> int:
    try:
        return _CAT_OPTIONS.index(val)
    except ValueError:
        return 3  # 待评估


def _prio_index(val: str) -> int:
    try:
        return PRIORITY_OPTIONS.index(val)
    except ValueError:
        return 1  # 中


def _qs_index(val: str) -> int:
    try:
        return QUERIT_STATUS_OPTIONS.index(val)
    except ValueError:
        return 3  # 待评估


# ── 逐条展示 ──────────────────────────────────────────────────
for rec in records:
    rec_id = rec["id"]
    title_display = rec.get("title") or f"（无标题，ID={rec_id}）"
    competitor = rec.get("competitor") or "—"
    pub_date = rec.get("publish_date") or "—"
    fetch_status = rec.get("fetch_status") or "pending"
    analysis_status = rec.get("analysis_status") or "pending"

    badge_text, _ = _FETCH_BADGE.get(fetch_status, ("", ""))
    analysis_label, _ = _ANALYSIS_BADGE.get(analysis_status, ("", ""))
    expander_label = f"[{competitor}] {title_display}  |  {pub_date}  {badge_text} {analysis_label}"

    with st.expander(expander_label, expanded=False):
        col_info, col_form = st.columns([1, 1])

        with col_info:
            st.markdown("**基本信息**")
            url = rec.get("source_url") or ""
            if url:
                st.markdown(f"原始链接：[查看原文]({url})")
            st.markdown(f"信息平台：{rec.get('source_platform') or '—'}")
            st.markdown(f"收录时间：{(rec.get('collected_at') or '')[:19]}")
            st.markdown(f"周次：{rec.get('week_id') or '—'}")

            st.markdown("**动态摘要**")
            st.write(rec.get("summary") or "（无摘要）")

            # ── 自动分析摘要 ──────────────────────────────────
            if analysis_status in ("analyzed", "partial"):
                st.markdown("---")
                st.markdown("**自动预分析**")
                a_label, a_color = _ANALYSIS_BADGE.get(analysis_status, (analysis_status, "#999"))
                confidence = rec.get("analysis_confidence") or 0.0
                st.markdown(
                    f'<span style="background:{a_color};color:#fff;border-radius:4px;'
                    f'padding:2px 8px;font-size:12px;">{a_label}</span>'
                    f'&nbsp;<small>置信度 {confidence:.0%}</small>',
                    unsafe_allow_html=True,
                )
                if rec.get("analysis_reason"):
                    st.caption(f"依据：{rec['analysis_reason'][:100]}")

                tags_raw = rec.get("secondary_tags")
                if tags_raw:
                    try:
                        tags = json.loads(tags_raw) if isinstance(tags_raw, str) else tags_raw
                        if tags:
                            st.caption("标签：" + "  ".join(f"`{t}`" for t in tags))
                    except Exception:
                        pass

            # ── 抓取信息 ──────────────────────────────────────
            if fetch_status != "pending":
                st.markdown("---")
                st.markdown("**抓取信息**")
                bl, bc = _FETCH_BADGE.get(fetch_status, (fetch_status, "#999"))
                st.markdown(
                    f'<span style="background:{bc};color:#fff;border-radius:4px;'
                    f'padding:2px 8px;font-size:12px;">{bl}</span>',
                    unsafe_allow_html=True,
                )
                if rec.get("fetch_error"):
                    st.caption(f"错误原因：{rec['fetch_error']}")
                if rec.get("raw_title"):
                    st.caption(f"原始标题：{rec['raw_title']}")
                if rec.get("raw_content"):
                    with st.expander("查看原始正文片段", expanded=False):
                        st.text(rec["raw_content"][:500])

                if url and fetch_status in ("failed", "partial", "restricted", "pending"):
                    if st.button("🔄 重新抓取并更新", key=f"refetch_{rec_id}"):
                        with st.spinner("抓取中..."):
                            res = refetch_and_update(rec_id, url)
                        if res["status"] in ("success", "partial"):
                            st.success(f"更新完成：{res['message']}")
                        else:
                            st.warning(f"抓取未成功：{res['message']}")
                        st.rerun()

            # ── GitHub 分析 ────────────────────────────────────
            if rec.get("github_event_type"):
                st.markdown("---")
                st.markdown("**GitHub 分析**")
                st.caption(f"类型：{rec.get('github_event_type','')} | 仓库：{rec.get('repository_name','')}")
                flags = []
                if rec.get("docs_changed"):      flags.append("📄 文档")
                if rec.get("capability_change"): flags.append("⚡ 产品能力")
                if rec.get("integration_change"): flags.append("🔗 生态集成")
                if rec.get("developer_experience_change"): flags.append("🛠 开发者体验")
                if flags:
                    st.markdown("  ".join(flags))
                if rec.get("change_summary"):
                    st.caption(rec["change_summary"])

        # ── 右侧：可编辑分析字段（自动建议直接预填）──────────────
        with col_form:
            st.markdown("**补充分析**")
            st.caption("人工字段有值时优先显示；为空时自动预填系统建议（可修改）")

            # 分类（含来源提示）
            cat_default = form_default(rec, "category", "auto_category", "待评估", {"待评估", ""})
            cat_hint = form_source_hint(rec, "category", "auto_category", {"待评估", ""})
            new_category = st.selectbox(
                "分类",
                _CAT_OPTIONS,
                index=_cat_index(cat_default),
                key=f"cat_{rec_id}",
            )
            st.caption(cat_hint)

            bv_default = form_default(rec, "business_value", "auto_business_value")
            new_business_value = st.text_area(
                "业务意义", value=bv_default,
                key=f"bv_{rec_id}", height=80,
            )

            qs_default = form_default(rec, "querit_status", "auto_querit_status",
                                      "待评估", {"待评估", ""})
            new_querit_status = st.selectbox(
                "Querit 当前状态", QUERIT_STATUS_OPTIONS,
                index=_qs_index(qs_default),
                key=f"qs_{rec_id}",
            )

            gap_default = form_default(rec, "gap_analysis", "auto_gap_analysis")
            new_gap = st.text_area(
                "差距判断", value=gap_default,
                key=f"gap_{rec_id}", height=70,
            )

            action_default = form_default(rec, "suggested_action", "auto_suggested_action")
            new_action = st.text_area(
                "建议动作", value=action_default,
                key=f"action_{rec_id}", height=70,
            )

            prio_default = form_default(rec, "priority", "auto_priority", "中", set())
            new_priority = st.selectbox(
                "优先级", PRIORITY_OPTIONS,
                index=_prio_index(prio_default),
                key=f"prio_{rec_id}",
            )

            new_manual_note = st.text_area(
                "人工备注", value=rec.get("manual_note") or "",
                key=f"note_{rec_id}", height=60,
            )

            # 操作按钮行
            btn_row = st.columns([1, 1, 1])

            with btn_row[0]:
                if st.button("🔍 重新分析", key=f"reanalyze_{rec_id}"):
                    fresh = analyze_record(rec)
                    database.update_record(rec_id, fresh.to_db_fields())
                    st.info("重新分析完成，已更新系统建议。")
                    st.rerun()

            with btn_row[1]:
                # 接受全部建议：将 auto_* 写入人工字段并保存到 DB
                if st.button("✔ 接受全部建议", key=f"accept_{rec_id}"):
                    auto_fields = {
                        "category":         rec.get("auto_category") or "待评估",
                        "business_value":   rec.get("auto_business_value") or "",
                        "querit_status":    rec.get("auto_querit_status") or "待评估",
                        "gap_analysis":     rec.get("auto_gap_analysis") or "",
                        "suggested_action": rec.get("auto_suggested_action") or "",
                        "priority":         rec.get("auto_priority") or "中",
                    }
                    database.update_record(rec_id, auto_fields)
                    st.success("系统建议已写入人工字段，请继续检查并确认。")
                    st.rerun()

        # ── 确认 / 忽略按钮 ───────────────────────────────────
        btn_col1, btn_col2, _ = st.columns([1, 1, 4])
        with btn_col1:
            if st.button("✅ 标记已确认", key=f"confirm_{rec_id}", type="primary"):
                updates = {
                    "category": new_category,
                    "business_value": new_business_value,
                    "querit_status": new_querit_status,
                    "gap_analysis": new_gap,
                    "suggested_action": new_action,
                    "priority": new_priority,
                    "manual_note": new_manual_note,
                }
                if confirm_record(rec_id, updates):
                    st.success("已确认，刷新页面生效")
                    st.rerun()
                else:
                    st.error("操作失败，请重试")

        with btn_col2:
            if st.button("🚫 标记已忽略", key=f"ignore_{rec_id}"):
                if ignore_record(rec_id):
                    st.info("已忽略，刷新页面生效")
                    st.rerun()
                else:
                    st.error("操作失败，请重试")
