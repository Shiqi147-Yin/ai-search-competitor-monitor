"""数据导入页面 — Phase 2（修订版）：四种录入方式，重复记录展示与重新抓取"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import streamlit as st
import pandas as pd
from datetime import datetime, timezone

import database
from config import (
    TEMPLATE_PATH, COMPETITORS, SOURCE_PLATFORMS,
    QUERIT_STATUS_OPTIONS, PRIORITY_OPTIONS,
)
from services.url_normalizer import normalize_url, is_valid_url, deduplicate_urls
from services.source_detector import detect_both
from services.url_fetcher import fetch_url
from services.github_analyzer import analyze_github_content
from services.import_batch_service import process_url_list, confirm_batch, BatchRecord
from services.flexible_excel_importer import parse_flexible_excel
from services.excel_importer import enrich_records
from services.data_service import batch_insert, get_current_week_id, refetch_and_update
from services.refetch_comparator import fetch_and_compare, apply_refetch_result, _STATUS_LABEL as _SL

st.set_page_config(page_title="数据导入", page_icon="📥", layout="wide")
st.title("📥 数据导入")

_DUP_STATUS_LABEL = {
    "": "已存在",
    "success": "已存在且信息完整",
    "partial": "已存在但信息不完整",
    "failed": "已存在但抓取失败",
    "restricted": "已存在但页面受限",
    "pending": "已存在",
    "duplicate": "已存在",
}


def _dup_status(r: "BatchRecord") -> str:
    if not r.is_duplicate:
        return ""
    fs = r.duplicate_fetch_status or ""
    return _DUP_STATUS_LABEL.get(fs, f"已存在（{fs}）")


_FETCH_STATUS_LABEL = {
    "success":    "✅ 成功",
    "partial":    "⚠️ 部分成功",
    "failed":     "❌ 失败",
    "restricted": "🔒 访问受限",
    "pending":    "⏳ 待抓取",
    "duplicate":  "🔁 重复",
}

# 哪些状态触发"需人工补充"提示
_NEEDS_MANUAL_STATUSES = {"restricted", "failed", "partial"}

tab1, tab2, tab3, tab4 = st.tabs(["快速添加链接", "批量添加链接", "上传 Excel", "导入记录"])


# ══════════════════════════════════════════════════════════════════
# Tab 1：快速添加链接
# ══════════════════════════════════════════════════════════════════
with tab1:
    st.subheader("单链接快速录入")
    url_input = st.text_input("输入 URL", placeholder="https://docs.tavily.com/changelog/...",
                              key="single_url")
    note_input = st.text_area("人工备注（可选）", height=80, key="single_note")

    if st.button("抓取并预览", key="fetch_single") and url_input.strip():
        url = url_input.strip()
        if not is_valid_url(url):
            st.error("URL 格式无效，请检查后重试")
        else:
            norm = normalize_url(url)
            if database.is_url_duplicate(norm):
                # ── 已存在：执行抓取并展示新旧对比 ──────────────────
                with st.spinner("已存在记录，正在执行本次抓取以对比..."):
                    comp = fetch_and_compare(url)

                if comp:
                    old_label = _SL.get(comp.existing_fetch_status, comp.existing_fetch_status)
                    new_label = _SL.get(comp.new_fetch_status, comp.new_fetch_status)

                    st.markdown("#### 数据库已有记录")
                    col_old, col_new = st.columns(2)
                    with col_old:
                        st.markdown("**已有记录**")
                        st.caption(f"ID：{comp.existing_id}")
                        st.caption(f"竞品：{comp.existing_competitor or '—'}")
                        st.caption(f"平台：{comp.existing_platform or '—'}")
                        st.caption(f"审核状态：{comp.existing_review_status or '—'}")
                        status_badge_old = {"restricted": "🔒", "failed": "❌", "success": "✅", "partial": "⚠️"}.get(comp.existing_fetch_status, "")
                        st.caption(f"抓取状态：{status_badge_old} {old_label}")
                        if comp.existing_fetch_error:
                            st.caption(f"错误：{comp.existing_fetch_error}")
                        st.caption(f"更新时间：{comp.existing_updated_at or '—'}")

                    with col_new:
                        st.markdown("**本次抓取**")
                        st.caption(f"抓取时间：{comp.fetched_at}")
                        st.caption(f"竞品：{comp.new_competitor or '—'}")
                        st.caption(f"平台：{comp.new_platform or '—'}")
                        status_badge_new = {"restricted": "🔒", "failed": "❌", "success": "✅", "partial": "⚠️"}.get(comp.new_fetch_status, "")
                        st.caption(f"抓取状态：{status_badge_new} {new_label}")
                        if comp.new_fetch_error:
                            st.caption(f"错误：{comp.new_fetch_error}")
                        if comp.new_title:
                            st.caption(f"标题：{comp.new_title[:60]}")
                        st.caption(f"需人工补充：{'是' if comp.new_needs_manual else '否'}")

                    if comp.status_changed:
                        st.info(comp.status_transition_msg)
                    else:
                        st.caption(comp.status_transition_msg)

                    btn1, btn2, btn3 = st.columns(3)
                    with btn1:
                        st.button("保持原记录", key=f"keep_{comp.existing_id}", disabled=True)
                    with btn2:
                        if st.button("📥 用本次结果更新已有记录", key=f"apply_refetch_{comp.existing_id}", type="primary"):
                            result = apply_refetch_result(comp)
                            if result["ok"]:
                                if result["old_status"] != result["new_status"]:
                                    st.success(
                                        f"已更新 ID={result['record_id']}  |  "
                                        f"{_SL.get(result['old_status'], result['old_status'])} → "
                                        f"{_SL.get(result['new_status'], result['new_status'])}  |  "
                                        f"更新时间：{result['updated_at']}"
                                    )
                                else:
                                    st.info(f"已更新 ID={result['record_id']}（状态无变化）  |  更新时间：{result['updated_at']}")
                                st.rerun()
                            else:
                                st.error(f"更新失败：{result['message']}")
                    with btn3:
                        st.caption(f"前往「待审核区」查看 ID={comp.existing_id}")
                else:
                    st.warning("该 URL 已存在于数据库中，未能读取已有记录。")
            else:
                with st.spinner("正在抓取页面信息..."):
                    detected = detect_both(url)
                    fr = fetch_url(url)
                    gh_info = {}
                    if detected["source_platform"] == "GitHub":
                        gh_info = analyze_github_content(
                            url, fr.title, fr.description, fr.content_snippet
                        )

                status_msg = _FETCH_STATUS_LABEL.get(fr.status, fr.status)
                if fr.status == "restricted":
                    st.warning(f"平台访问受限（{fr.error}），已保留链接，请人工补充内容。")
                elif fr.error:
                    st.info(f"抓取状态：{status_msg}  |  原因：{fr.error}")
                else:
                    st.info(f"抓取状态：{status_msg}")

                st.subheader("确认并编辑信息")
                with st.form("single_confirm_form"):
                    c1, c2 = st.columns(2)
                    with c1:
                        new_competitor = st.selectbox(
                            "竞品", COMPETITORS,
                            index=COMPETITORS.index(detected["competitor"])
                                  if detected["competitor"] in COMPETITORS else len(COMPETITORS) - 1,
                        )
                        new_platform = st.selectbox(
                            "信息平台", SOURCE_PLATFORMS,
                            index=SOURCE_PLATFORMS.index(detected["source_platform"])
                                  if detected["source_platform"] in SOURCE_PLATFORMS else len(SOURCE_PLATFORMS) - 1,
                        )
                        new_title = st.text_input("标题", value=fr.title or "")
                    with c2:
                        new_date = st.text_input("发布时间", value=fr.published_date or "",
                                                 placeholder="YYYY-MM-DD")
                        new_summary = st.text_area("动态概述", value=fr.description or "", height=120)

                    if gh_info:
                        st.markdown("**GitHub 分析（可参考）**")
                        st.caption(f"类型：{gh_info.get('github_event_type','')} | "
                                   f"仓库：{gh_info.get('repository_name','')} | "
                                   f"变化摘要：{gh_info.get('change_summary','')}")

                    submitted = st.form_submit_button("✅ 确认加入待审核区", type="primary")

                if submitted:
                    now = datetime.now(timezone.utc).isoformat()
                    rec = {
                        "source_url": url,
                        "normalized_url": norm,
                        "final_url": fr.final_url or url,
                        "competitor": new_competitor,
                        "source_platform": new_platform,
                        "title": new_title or url,
                        "summary": new_summary,
                        "publish_date": new_date or None,
                        "raw_title": fr.title,
                        "raw_content": fr.content_snippet[:2000] if fr.content_snippet else None,
                        "content_source": fr.content_source,
                        "fetch_status": fr.status,
                        "fetch_error": fr.error or None,
                        "manual_note": note_input or None,
                        "collected_at": now,
                        "week_id": get_current_week_id(),
                        "review_status": "待审核",
                        "source_mode": "manual",
                        "discovery_method": "manual",
                        "category": "待评估",
                        "querit_status": "待评估",
                        "priority": "中",
                        "follow_up_status": "待处理",
                        "updated_at": now,
                        **{k: v for k, v in gh_info.items()},
                    }
                    status = database.insert_record(rec)
                    if status == "success":
                        st.success("已加入待审核区！")
                    elif status == "duplicate":
                        # 写入时发现重复：展示对比（已在上方 is_url_duplicate 分支处理）
                        st.info("该 URL 已存在于数据库中，请使用上方对比区域更新已有记录。")
                    else:
                        st.error(f"写入失败：{status}")


# ══════════════════════════════════════════════════════════════════
# Tab 2：批量添加链接
# ══════════════════════════════════════════════════════════════════
with tab2:
    st.subheader("批量添加链接")
    st.caption("每行输入一个 URL，支持粘贴多行")
    bulk_text = st.text_area("批量 URL 输入", height=200,
                              placeholder="https://docs.tavily.com/...\nhttps://exa.ai/blog/...",
                              key="bulk_urls")

    if st.button("开始抓取", key="fetch_bulk") and bulk_text.strip():
        raw_lines = [l.strip() for l in bulk_text.strip().splitlines()]
        raw_lines = [l for l in raw_lines if l]

        if not raw_lines:
            st.warning("未检测到有效 URL")
        else:
            progress_bar = st.progress(0)
            status_text = st.empty()

            def _cb(cur, total):
                if total > 0:
                    progress_bar.progress(cur / total)
                    status_text.text(f"正在处理 {cur}/{total}...")

            with st.spinner("逐条抓取中，请稍候..."):
                batch_records = process_url_list(raw_lines, progress_callback=_cb)

            progress_bar.empty()
            status_text.empty()
            st.session_state["batch_records"] = batch_records
            st.success(f"抓取完成，共处理 {len(batch_records)} 条")

    if "batch_records" in st.session_state and st.session_state["batch_records"]:
        records: list[BatchRecord] = st.session_state["batch_records"]

        # 构建展示 DataFrame
        rows = []
        for i, r in enumerate(records):
            if r.is_duplicate:
                status_text_val = _dup_status(r)
                comp_val = r.competitor  # 已填充真实或识别的值
                plat_val = r.source_platform
                title_val = (r.duplicate_title or "")[:50]
                error_val = ""
                rec_id_val = r.duplicate_record_id or ""
                review_val = r.duplicate_review_status or ""
                updated_val = r.duplicate_updated_at or ""
            else:
                status_text_val = _FETCH_STATUS_LABEL.get(r.fetch_status, r.fetch_status)
                comp_val = r.competitor
                plat_val = r.source_platform
                title_val = r.title[:50] if r.title else ""
                # restricted 显示中性提示而非红色错误
                if r.fetch_status == "restricted":
                    error_val = "访问受限，需人工补充"
                else:
                    error_val = r.fetch_error[:50] if r.fetch_error else ""
                rec_id_val = ""
                review_val = ""
                updated_val = ""

            rows.append({
                "_idx": i,
                "URL": r.original_url[:60] + "..." if len(r.original_url) > 60 else r.original_url,
                "竞品": comp_val,
                "平台": plat_val,
                "标题": title_val,
                "发布时间": r.published_date or "",
                "HTTP状态": r.fetch_status if not r.is_duplicate else "",
                "状态": status_text_val,
                "已有ID": rec_id_val,
                "审核状态": review_val,
                "最后更新": updated_val,
                "错误": error_val,
            })
        df_show = pd.DataFrame(rows)
        st.dataframe(df_show.drop(columns=["_idx"]), use_container_width=True, height=350)

        dup_records = [r for r in records if r.is_duplicate]
        importable = [r for r in records if not r.is_duplicate and not r.is_invalid_url]
        st.caption(
            f"可导入：{len(importable)} 条  |  "
            f"已存在：{len(dup_records)} 条  |  "
            f"失败/受限：{sum(1 for r in records if not r.is_duplicate and r.fetch_status in ('failed','restricted'))} 条"
        )

        # 重新抓取区域（针对已存在但抓取失败/不完整的记录）
        refetch_candidates = [r for r in records if r.is_duplicate
                              and r.duplicate_fetch_status in ("failed", "partial", "pending", "")]
        if refetch_candidates:
            st.markdown("---")
            st.markdown(f"**{len(refetch_candidates)} 条已有记录抓取失败或信息不完整，可重新抓取：**")
            for r in refetch_candidates:
                col_a, col_b = st.columns([4, 1])
                with col_a:
                    st.caption(
                        f"ID={r.duplicate_record_id}  |  {r.original_url[:70]}  |  "
                        f"状态：{_dup_status(r)}"
                    )
                with col_b:
                    if st.button("重新抓取", key=f"refetch_bulk_{r.duplicate_record_id}"):
                        with st.spinner("抓取中..."):
                            res = refetch_and_update(r.duplicate_record_id, r.original_url)
                        if res["status"] in ("success", "partial"):
                            st.success(f"ID={r.duplicate_record_id} 更新完成")
                        else:
                            st.warning(f"ID={r.duplicate_record_id}：{res['message']}")

        import_all = st.checkbox("全部选中（含抓取失败/受限，以链接保留形式写入）", value=True)
        if not import_all:
            success_only = st.checkbox("仅选择抓取成功和部分成功的记录", value=True)
        else:
            success_only = False

        if st.button("批量确认加入待审核区", type="primary", key="confirm_bulk"):
            if success_only:
                selected = [i for i, r in enumerate(records)
                            if r.fetch_status in ("success", "partial") and not r.is_duplicate]
            else:
                selected = [i for i, r in enumerate(records) if not r.is_duplicate and not r.is_invalid_url]

            if not selected:
                st.warning("没有可导入的记录")
            else:
                result = confirm_batch(records, selected, import_mode="url_batch")
                c1, c2, c3, c4 = st.columns(4)
                c1.metric("最终导入", result["final_imported"])
                c2.metric("重复跳过", result["duplicate"])
                c3.metric("抓取失败", result["failed"])
                c4.metric("受限页面", result["restricted"])
                st.success(f"已写入待审核区，批次 ID：{result['batch_id']}")
                del st.session_state["batch_records"]


# ══════════════════════════════════════════════════════════════════
# Tab 3：上传 Excel
# ══════════════════════════════════════════════════════════════════
with tab3:
    st.subheader("上传 Excel 文件")

    # 模板下载
    if TEMPLATE_PATH.exists():
        with open(TEMPLATE_PATH, "rb") as f:
            st.download_button("下载标准模板", data=f.read(),
                               file_name="competitor_updates_template.xlsx",
                               mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

    st.caption("支持：① 完整标准模板（7列） ② 简单链接表（至少含 URL 列）")
    uploaded = st.file_uploader("选择 .xlsx 文件", type=["xlsx"], key="excel_upload")

    if uploaded:
        if not uploaded.name.lower().endswith(".xlsx"):
            st.error("请上传 .xlsx 格式文件")
        else:
            file_bytes = uploaded.read()
            records_raw, excel_type, errors = parse_flexible_excel(file_bytes)

            if excel_type == "full_template":
                st.info("检测到：**完整标准模板**，使用标准解析逻辑")
            elif excel_type == "simple_url_table":
                st.info("检测到：**简单链接表**，将通过 URL 抓取补充缺失信息")
            else:
                st.error("无法识别 Excel 格式")

            if errors:
                st.warning(f"{len(errors)} 个问题：")
                for e in errors:
                    st.markdown(f"- {e}")

            if records_raw:
                if excel_type == "full_template":
                    # 完整模板：走 enrich_records
                    import pandas as pd
                    df = pd.DataFrame(records_raw)
                    df_enriched = enrich_records(df)
                    st.subheader("预览（完整模板）")
                    st.dataframe(df_enriched[["publish_date","competitor","title","source_url","source_platform"]],
                                 use_container_width=True, height=300)
                    if st.button("确认导入（完整模板）", type="primary"):
                        result = batch_insert(df_enriched.to_dict(orient="records"))
                        st.metric("成功", result["success"])
                        st.metric("重复", result["duplicate"])
                        st.metric("失败", result["error"])
                        if result["success"] > 0:
                            st.success("已写入待审核区")

                elif excel_type == "simple_url_table":
                    url_list = [r.get("source_url", "") for r in records_raw if r.get("source_url")]
                    st.caption(f"共识别 {len(url_list)} 个 URL")
                    if st.button("开始抓取并预览", key="excel_fetch"):
                        with st.spinner("抓取中..."):
                            batch_recs = process_url_list(url_list)
                        st.session_state["excel_batch_records"] = batch_recs
                        st.session_state["excel_raw_records"] = records_raw

                    if "excel_batch_records" in st.session_state:
                        b_recs: list[BatchRecord] = st.session_state["excel_batch_records"]
                        rows = [{"URL": r.original_url[:60], "竞品": r.competitor,
                                 "标题": r.title[:50], "状态": _FETCH_STATUS_LABEL.get(r.fetch_status,"")}
                                for r in b_recs]
                        st.dataframe(pd.DataFrame(rows), use_container_width=True, height=300)
                        if st.button("确认导入（简单链接表）", type="primary", key="confirm_excel"):
                            selected = [i for i, r in enumerate(b_recs) if not r.is_duplicate and not r.is_invalid_url]
                            result = confirm_batch(b_recs, selected, import_mode="manual_excel")
                            st.metric("最终导入", result["final_imported"])
                            st.metric("重复", result["duplicate"])
                            st.success(f"已写入待审核区，批次 ID：{result['batch_id']}")
                            del st.session_state["excel_batch_records"]


# ══════════════════════════════════════════════════════════════════
# Tab 4：导入记录
# ══════════════════════════════════════════════════════════════════
with tab4:
    st.subheader("导入批次记录")
    batches = database.get_batches()
    if not batches:
        st.info("暂无导入记录")
    else:
        MODE_LABEL = {
            "manual_form": "单链接",
            "url_batch": "批量链接",
            "manual_excel": "Excel上传",
        }
        df_batches = pd.DataFrame(batches)
        df_batches["import_mode"] = df_batches["import_mode"].map(
            lambda m: MODE_LABEL.get(m, m)
        )
        df_batches["created_at"] = df_batches["created_at"].str[:19].str.replace("T", " ")
        rename = {
            "batch_id": "批次ID", "created_at": "导入时间", "import_mode": "方式",
            "total": "总数", "success": "成功", "partial": "部分成功",
            "failed": "失败", "restricted": "受限", "duplicate": "重复",
            "final_imported": "最终导入",
        }
        st.dataframe(df_batches.rename(columns=rename), use_container_width=True)
