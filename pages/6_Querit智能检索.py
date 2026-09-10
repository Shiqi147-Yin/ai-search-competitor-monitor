"""Querit 智能检索页面（含新鲜度过滤 + 相关性分级 + Benchmark 模式）"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from env_loader import load_env, get_env_bool
load_env()

import streamlit as st
import pandas as pd
from datetime import datetime, timezone, timedelta

import database
from services.querit_query_builder import generate_queries, is_english_query
from services.querit_client import search, check_config, is_mock_mode
from services.querit_result_adapter import adapt_results
from services.content_analyzer import analyze_record
from services.freshness_filter import check_freshness, freshness_summary, FreshnessResult
from services.benchmark_matcher import load_benchmark, evaluate_recall
from services.competitor_relevance_filter import classify_relevance, classify_source_authority
from services.data_service import batch_insert

st.set_page_config(page_title="Querit 智能检索", page_icon="🔭", layout="wide")
st.title("🔭 Querit 智能检索")

_MOCK_MODE = is_mock_mode()
if _MOCK_MODE:
    st.warning("当前为 Mock 测试模式，结果为模拟数据。设置 QUERIT_MOCK_MODE=false 后使用真实 API。")
else:
    ok, err = check_config()
    if not ok:
        st.error(f"API 配置不完整：{err}")
        st.stop()
    else:
        st.success("当前为真实 API 模式。")

database.init_db()
database.run_migrations()

SOURCE_OPTIONS = ["All", "官网", "Blog", "Docs", "GitHub", "X", "LinkedIn", "Event"]
COMPETITOR_OPTIONS = ["All", "Tavily", "Exa", "Brave"]

_FRESHNESS_ICON = {
    "within_window": "✅ 时间窗口内",
    "outside_window": "❌ 超出时间窗口",
    "date_missing": "⚠ 日期待确认",
    "future_date": "⚠ 疑似未来时间",
    "date_invalid": "⚠ 日期解析失败",
}

_AUTHORITY_ICON = {
    "official": "🏛 官方",
    "first_party_ecosystem": "🤝 一方生态",
    "reputable_third_party": "📰 可信三方",
    "unknown": "❓ 未知",
    "low_value_aggregator": "🗑 低价值聚合",
}

_TARGET_ICON = {
    "exact_target": "🎯 精确匹配",
    "likely_target": "✅ 高置信匹配",
    "third_party_relevant": "📌 第三方相关",
    "weak_match": "~弱匹配",
    "unrelated": "✗ 无关",
}

st.markdown("## 检索设置")
col1, col2, col3 = st.columns(3)
with col1:
    sel_competitors = st.multiselect("竞品", COMPETITOR_OPTIONS, default=["Tavily"], key="q_competitors")
    time_window = st.selectbox("时间范围（天）", [7, 14, 30], index=0, key="q_time")
with col2:
    sel_sources = st.multiselect("来源范围", SOURCE_OPTIONS, default=["All"], key="q_sources")
    result_per_query = st.number_input("每条 Query 返回数", min_value=1, max_value=20, value=10, key="q_num")
with col3:
    max_total = st.number_input("最大总结果数", min_value=5, max_value=200, value=50, key="q_max")
    benchmark_mode = st.checkbox("Benchmark 验证模式", value=False, key="bench_mode")

extra_prompt = st.text_input("可选补充要求（英文）", key="q_extra")

btn_gen, btn_run = st.columns(2)
with btn_gen:
    gen_clicked = st.button("生成英文 Query", key="btn_gen")
with btn_run:
    run_clicked = st.button("开始 Querit 检索", key="btn_run", type="primary")

competitors = (
    ["Tavily", "Exa", "Brave"] if "All" in (sel_competitors or [])
    else [c for c in sel_competitors if c != "All"]
) or ["Tavily"]
sources = sel_sources or ["All"]

if gen_clicked:
    reference_time = datetime.now(timezone.utc)
    queries = generate_queries(competitors, int(time_window), sources, reference_time)
    if extra_prompt.strip():
        for q in queries:
            q["generated_query"] += f" {extra_prompt.strip()}"
    st.session_state["search_queries"] = queries
    st.session_state["search_reference_time"] = reference_time.isoformat()

if "search_queries" in st.session_state:
    st.markdown("## 英文 Query 预览")
    ref_ts = st.session_state.get("search_reference_time", "")
    if ref_ts:
        ref_dt = datetime.fromisoformat(ref_ts.replace("Z", "+00:00"))
        start_dt = ref_dt - timedelta(days=int(time_window))
        st.caption(f"时间基准：{ref_dt.date()}  |  窗口：{time_window} 天  |  有效范围：{start_dt.date()} 至 {ref_dt.date()}")
    queries = st.session_state["search_queries"]
    updated_queries = []
    for i, q in enumerate(queries):
        col_q, col_del = st.columns([11, 1])
        with col_q:
            edited = st.text_area(
                f"[{q['competitor']}] {q['query_type']} ({q.get('source_target', '')})",
                value=q["generated_query"], height=80, key=f"qedit_{i}",
            )
            if not is_english_query(edited):
                st.warning(f"Query {i+1}：请使用英文。")
        with col_del:
            if not st.button("X", key=f"qdel_{i}"):
                updated_queries.append({**q, "generated_query": edited})
    custom_q = st.text_input("新增自定义英文 Query", key="custom_q")
    if st.button("添加 Query", key="add_cq") and custom_q.strip():
        updated_queries.append({
            "generated_query": custom_q.strip(), "query_type": "custom",
            "source_target": "custom", "competitor": competitors[0] if competitors else "Other",
            "source_scope": sources, "time_window": time_window,
        })
    st.session_state["search_queries"] = updated_queries

if run_clicked and "search_queries" in st.session_state:
    queries_to_run = st.session_state["search_queries"]
    if not queries_to_run:
        st.warning("没有可执行的 Query。")
    else:
        st.markdown("## 检索运行状态")
        reference_time = datetime.now(timezone.utc)
        now_iso = reference_time.isoformat()
        window_start = (reference_time - timedelta(days=int(time_window))).strftime("%Y-%m-%dT%H:%M:%SZ")
        window_end = reference_time.strftime("%Y-%m-%dT%H:%M:%SZ")

        run_id = database.create_search_run({
            "started_at": now_iso, "status": "running",
            "competitor_scope": ",".join(competitors),
            "source_scope": ",".join(sources),
            "time_window_days": int(time_window),
            "window_start": window_start, "window_end": window_end,
            "requested_result_count": int(result_per_query),
            "query_count": len(queries_to_run),
            "created_at": now_iso,
        })
        mode_str = "Mock" if _MOCK_MODE else "真实 API"
        bench_str = " | Benchmark 模式" if benchmark_mode else ""
        st.info(f"Run ID: {run_id} | 窗口: {window_start[:10]} 至 {window_end[:10]} | {mode_str}{bench_str}")

        all_adapted = []
        success_count = fail_count = 0
        seen_norm: set[str] = set()
        prog = st.progress(0)
        stat_area = st.empty()

        # 加载基准（benchmark 模式）
        bm_events = []
        if benchmark_mode and competitors:
            bm_events = load_benchmark(competitors[0])

        for idx, qinfo in enumerate(queries_to_run):
            q_text = qinfo["generated_query"]
            q_comp = qinfo.get("competitor", "Other")
            qt = qinfo.get("query_type", "")
            prog.progress((idx + 1) / len(queries_to_run))
            stat_area.text(f"执行 Query {idx+1}/{len(queries_to_run)} [{qt}]: {q_text[:60]}...")

            qid = database.create_search_query({
                "run_id": run_id, "generated_query": q_text, "executed_query": q_text,
                "query_type": qt, "competitor": q_comp,
                "source_scope": ",".join(qinfo.get("source_scope", sources) or sources),
                "status": "running", "created_at": now_iso,
            })

            run_res = search(q_text, int(result_per_query))

            if run_res.success:
                success_count += 1
                database.update_search_query(qid, {
                    "status": "success", "result_count": len(run_res.results),
                    "duration_ms": run_res.duration_ms,
                })
                adapted = adapt_results(run_res.results, str(run_id), qid, q_comp)
                for rec in adapted:
                    try:
                        an = analyze_record(rec)
                        rec.update(an.to_db_fields())
                        rec["_analysis"] = an
                    except Exception:
                        pass
                    # 新鲜度
                    fr = check_freshness(rec, int(time_window), reference_time)
                    rec["_freshness"] = fr
                    # 相关性
                    from services.benchmark_matcher import match_result_to_events
                    m_id, m_type, m_score = match_result_to_events(rec, bm_events) if bm_events else (None, "no_match", 0.0)
                    relevance = classify_relevance(rec, q_comp, m_type, m_score)
                    rec.update(relevance)
                    # 批次内去重
                    norm = rec.get("normalized_url", "")
                    rec["_is_dedup_run"] = norm in seen_norm
                    if norm:
                        seen_norm.add(norm)
                    # 最终默认选择
                    rec["_should_select"] = (
                        fr.freshness_status == "within_window" and
                        not rec.get("_is_duplicate") and
                        not rec.get("_is_dedup_run") and
                        relevance.get("official_source", False) and
                        relevance.get("target_match_status") in ("exact_target", "likely_target")
                    )
                    # 写预览表
                    database.insert_search_result({
                        "run_id": run_id, "query_id": qid,
                        "title": rec.get("title", ""),
                        "source_url": rec.get("source_url", ""),
                        "normalized_url": rec.get("normalized_url", ""),
                        "raw_summary": rec.get("summary", ""),
                        "published_date": rec.get("published_date") or rec.get("publish_date") or "",
                        "score": rec.get("querit_score"),
                        "rank": rec.get("querit_rank", 0),
                        "competitor": rec.get("competitor", ""),
                        "source_platform": rec.get("source_platform", ""),
                        "duplicate": 1 if rec.get("_is_duplicate") else 0,
                        "existing_record_id": rec.get("_existing_record_id", 0),
                        "normalized_published_at": fr.normalized_published_at,
                        "raw_published_date": fr.raw_published_date,
                        "date_status": fr.date_status,
                        "date_source": fr.date_source,
                        "date_confidence": fr.date_confidence,
                        "freshness_status": fr.freshness_status,
                        "days_from_search": fr.days_from_search,
                        "freshness_reason": fr.freshness_reason,
                        "window_start": window_start,
                        "window_end": window_end,
                        "created_at": now_iso,
                    })
                all_adapted.extend(adapted)
            else:
                fail_count += 1
                database.update_search_query(qid, {"status": "failed", "error_message": run_res.error})
                st.warning(f"Query 失败 [{qt}]: {run_res.error}")

        prog.empty()
        stat_area.empty()
        total_before = len(all_adapted)
        all_adapted = all_adapted[:int(max_total)]
        unique_c = len({r.get("normalized_url") for r in all_adapted})
        fr_list = [r.get("_freshness") for r in all_adapted if r.get("_freshness")]
        fr_stats = freshness_summary(fr_list) if fr_list else {}
        official_cnt = sum(1 for r in all_adapted if r.get("official_source"))
        low_val_cnt = sum(1 for r in all_adapted if r.get("source_authority") == "low_value_aggregator")

        database.update_search_run(run_id, {
            "status": "completed",
            "completed_at": datetime.now(timezone.utc).isoformat(),
            "actual_result_count": total_before,
            "unique_result_count": unique_c,
            "success_query_count": success_count,
            "failed_query_count": fail_count,
            "within_window_count": fr_stats.get("within_window", 0),
            "outside_window_count": fr_stats.get("outside_window", 0),
            "missing_date_count": fr_stats.get("date_missing", 0),
            "invalid_date_count": fr_stats.get("date_invalid", 0),
            "future_date_count": fr_stats.get("future_date", 0),
        })

        st.success(
            f"检索完成 | 总: {total_before} | 去重后: {unique_c} | "
            f"窗口内: {fr_stats.get('within_window',0)} | "
            f"超期: {fr_stats.get('outside_window',0)} | 缺日期: {fr_stats.get('date_missing',0)}"
        )
        st.session_state["run_results"] = all_adapted
        st.session_state["run_id"] = run_id
        st.session_state["run_time_window"] = int(time_window)
        st.session_state["run_reference_time"] = reference_time
        st.session_state["run_bm_events"] = bm_events

if "run_results" in st.session_state and st.session_state["run_results"]:
    results = st.session_state["run_results"]
    bm_events_display = st.session_state.get("run_bm_events", [])

    # ── 顶部统计 ─────────────────────────────────────────────
    fr_list_all = [r.get("_freshness") for r in results if r.get("_freshness")]
    stats = freshness_summary(fr_list_all) if fr_list_all else {}
    official_n = sum(1 for r in results if r.get("official_source"))
    third_party_n = sum(1 for r in results if r.get("source_authority") in ("reputable_third_party", "first_party_ecosystem"))
    low_val_n = sum(1 for r in results if r.get("source_authority") == "low_value_aggregator")

    mc1, mc2, mc3, mc4, mc5, mc6, mc7 = st.columns(7)
    mc1.metric("原始结果", len(results))
    mc2.metric("✅ 窗口内", stats.get("within_window", 0))
    mc3.metric("❌ 超期", stats.get("outside_window", 0))
    mc4.metric("⚠ 日期缺失", stats.get("date_missing", 0))
    mc5.metric("🏛 官方来源", official_n)
    mc6.metric("📰 三方/生态", third_party_n)
    mc7.metric("🗑 低价值", low_val_n)

    # Benchmark 召回面板
    if bm_events_display:
        st.markdown("### Benchmark 召回评估")
        competitor_for_recall = results[0].get("competitor", "Tavily") if results else "Tavily"
        recall_result = evaluate_recall(
            [r for r in results if not r.get("_is_dedup_run")],
            competitor_for_recall,
        )
        bc1, bc2, bc3, bc4 = st.columns(4)
        bc1.metric("基准事件数", recall_result["expected_count"])
        bc2.metric("已召回", recall_result["recalled_count"])
        bc3.metric("未召回", recall_result["missed_count"])
        bc4.metric("召回率", f"{recall_result['recall_rate']:.0%}")
        if recall_result["missed_events"]:
            with st.expander(f"未召回事件 ({len(recall_result['missed_events'])} 条)  — 点击可诊断"):
                for ev in recall_result["missed_events"]:
                    col_ev, col_diag = st.columns([4, 1])
                    with col_ev:
                        st.markdown(f"- **{ev['title']}** — [{ev['url'][:60]}]({ev['url']})")
                    with col_diag:
                        diag_key = f"diag_{ev['id']}"
                        if st.button("诊断漏召回", key=diag_key):
                            st.session_state[f"diag_result_{ev['id']}"] = None
                            with st.spinner(f"正在诊断「{ev['title']}」…"):
                                from services.benchmark_diagnostics import diagnose_missed_event
                                from services.benchmark_matcher import load_benchmark
                                bm_events_all = load_benchmark(competitor_for_recall)
                                ev_full = next((e for e in bm_events_all if e["id"] == ev["id"]), None)
                                if ev_full:
                                    diag_result = diagnose_missed_event(ev_full, num_results=5)
                                    st.session_state[f"diag_result_{ev['id']}"] = diag_result

                    # 显示诊断结果
                    dr = st.session_state.get(f"diag_result_{ev['id']}")
                    if dr:
                        with st.container():
                            st.markdown(f"**诊断结论：`{dr.final_diagnosis}`**")
                            st.caption(dr.diagnosis_reason)
                            for vr in dr.variants:
                                found = "✅" if (vr.target_url_found or vr.target_title_found) else "❌"
                                st.caption(
                                    f"[{vr.variant_name}] {found}  "
                                    f"结果数: {vr.result_count}  |  "
                                    f"{vr.executed_query[:70]}"
                                )

    st.markdown("## 结果预览")
    filter_view = st.radio(
        "显示范围", ["全部结果", "仅时间窗口内", "仅官方来源", "仅日期待确认", "仅低价值结果"],
        horizontal=True, key="filter_view",
    )

    rows = []
    for i, rec in enumerate(results):
        fr = rec.get("_freshness")
        freshness_icon = _FRESHNESS_ICON.get(fr.freshness_status if fr else "date_missing", "?")
        auth = rec.get("source_authority", "unknown")
        authority_icon = _AUTHORITY_ICON.get(auth, auth)
        target_icon = _TARGET_ICON.get(rec.get("target_match_status", "weak_match"), "?")

        if filter_view == "仅时间窗口内" and (not fr or fr.freshness_status != "within_window"):
            continue
        if filter_view == "仅官方来源" and not rec.get("official_source"):
            continue
        if filter_view == "仅日期待确认" and (not fr or fr.freshness_status != "date_missing"):
            continue
        if filter_view == "仅低价值结果" and auth != "low_value_aggregator":
            continue

        pub_date = ""
        if fr:
            pub_date = (fr.normalized_published_at or fr.raw_published_date)[:10] if (fr.normalized_published_at or fr.raw_published_date) else ""
        if not pub_date:
            pub_date = (rec.get("published_date") or rec.get("publish_date") or "")[:10]

        rows.append({
            "_idx": i,
            "选择": rec.get("_should_select", False),
            "标题": (rec.get("title") or "")[:50],
            "URL": (rec.get("source_url") or "")[:60],
            "竞品": rec.get("competitor", ""),
            "来源": rec.get("source_platform", ""),
            "来源权威": authority_icon,
            "目标匹配": target_icon,
            "发布时间": pub_date,
            "时间状态": freshness_icon,
            "距今(天)": fr.days_from_search if (fr and fr.days_from_search is not None) else "",
            "重复": "是" if (rec.get("_is_duplicate") or rec.get("_is_dedup_run")) else "",
            "分类": rec.get("auto_category") or "",
        })

    if not rows:
        st.info("当前视图无结果。")
    else:
        df = pd.DataFrame(rows)
        edited_df = st.data_editor(
            df.drop(columns=["_idx"]),
            column_config={"选择": st.column_config.CheckboxColumn("选择", default=False)},
            use_container_width=True, height=420, key="res_editor",
        )

        st.markdown("## 确认导入")
        filter_pri = st.checkbox("只导入高/中优先级", value=False)
        allow_outside = st.checkbox("允许导入超期结果（需二次确认）", value=False)

        if st.button("确认加入待审核区", type="primary"):
            selected = edited_df[edited_df["选择"] == True].index.tolist()
            to_import = []
            for df_idx in selected:
                orig_idx = rows[df_idx]["_idx"]
                rec = results[orig_idx]
                fr = rec.get("_freshness")
                if rec.get("_is_duplicate") or rec.get("_is_dedup_run"):
                    continue
                if filter_pri and rec.get("auto_priority", "中") not in ("高", "中"):
                    continue
                if fr and fr.freshness_status == "outside_window" and not allow_outside:
                    continue
                to_import.append({k: v for k, v in rec.items()
                                   if not k.startswith("_") and k != "_analysis"})
            if not to_import:
                st.warning("没有符合条件的记录可导入。")
            else:
                stat = batch_insert(to_import)
                c1, c2, c3 = st.columns(3)
                c1.metric("成功导入", stat["success"])
                c2.metric("重复跳过", stat["duplicate"])
                c3.metric("失败", stat["error"])
                if stat["success"] > 0:
                    st.success(f"已将 {stat['success']} 条加入待审核区！")
                    database.update_search_run(st.session_state["run_id"],
                                               {"selected_result_count": stat["success"]})
                    del st.session_state["run_results"]

st.divider()
st.markdown("## 历史检索批次")
runs = database.get_search_runs(limit=10)
if not runs:
    st.caption("暂无检索记录。")
else:
    df_runs = pd.DataFrame(runs)
    rename = {
        "id": "Run ID", "started_at": "开始时间", "status": "状态",
        "competitor_scope": "竞品", "time_window_days": "窗口(天)",
        "query_count": "Query数", "actual_result_count": "结果数",
        "within_window_count": "窗口内", "outside_window_count": "超期",
        "missing_date_count": "缺日期", "selected_result_count": "导入数",
    }
    show = [c for c in rename if c in df_runs.columns]
    st.dataframe(df_runs[show].rename(columns=rename), use_container_width=True, hide_index=True)
