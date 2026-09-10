"""来源能力测试页面（不写入正式看板数据库）"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import io
from datetime import datetime, timezone

import streamlit as st
import pandas as pd
import yaml

from services.url_normalizer import normalize_url, is_valid_url
from services.source_detector import detect_both
from services.url_fetcher import fetch_url
from services.github_fetcher import fetch_github
from services.github_analyzer import analyze_github_content
from services.source_capability_classifier import (
    classify_fetch_result, list_all_capabilities, get_fetch_strategy,
)

st.set_page_config(page_title="来源能力测试", page_icon="🔬", layout="wide")
st.title("🔬 来源能力测试")
st.caption("测试指定 URL 的自动抓取能力，不写入正式看板数据库。")

_TEST_URL_CONFIG = Path(__file__).parent.parent / "config" / "source_test_urls.yaml"


def _load_preset_urls() -> dict:
    try:
        with open(_TEST_URL_CONFIG, encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    except Exception:
        return {}


def _flatten_preset_urls(data: dict) -> list[str]:
    urls = []
    for competitor_data in data.values():
        if isinstance(competitor_data, dict):
            for source_urls in competitor_data.values():
                if isinstance(source_urls, list):
                    urls.extend([u for u in source_urls if u])
    return urls


def _run_single_test(url: str) -> dict:
    norm = normalize_url(url)
    detected = detect_both(url)
    platform = detected["source_platform"]
    strategy = get_fetch_strategy(platform)

    title = description = published_date = content_snippet = ""
    fetch_status = "pending"
    fetch_error = ""
    http_status = ""
    final_url = url
    redirected = "否"
    gh_info: dict = {}
    commits_summary = ""

    if platform == "GitHub":
        # GitHub 专项处理
        gfr = fetch_github(url)
        title = gfr.title
        description = gfr.description
        published_date = gfr.published_date
        content_snippet = gfr.content_snippet
        fetch_status = gfr.status
        fetch_error = gfr.error
        http_status = str(gfr.raw_api_status) if gfr.raw_api_status else ""
        gh_info = gfr.change_analysis or {}
        if gfr.commits:
            commits_summary = "; ".join(c.title for c in gfr.commits[:3])
            content_snippet = content_snippet or commits_summary
        # 如果 URL 标题为空，用 detected.both 补全
        if not title:
            detected = detect_both(url, title, description)
        else:
            detected = detect_both(url, title, description)
    else:
        fr = fetch_url(url)
        title = fr.title
        description = fr.description
        published_date = fr.published_date
        content_snippet = fr.content_snippet
        fetch_status = fr.status
        fetch_error = fr.error
        http_status = str(fr.http_status_code) if fr.http_status_code else ""
        final_url = fr.final_url or url
        redirected = "是" if (fr.final_url and fr.final_url != url) else "否"
        detected = detect_both(url, title, description)

    cap = classify_fetch_result(
        fetch_status=fetch_status,
        has_title=bool(title),
        has_description=bool(description),
        has_published_date=bool(published_date),
        source_platform=platform,
    )

    needs_manual_fields = []
    if not title:
        needs_manual_fields.append("标题")
    if not published_date:
        needs_manual_fields.append("发布时间")
    if not description:
        needs_manual_fields.append("摘要")

    return {
        "tested_at": datetime.now(timezone.utc).isoformat()[:19].replace("T", " "),
        "url": url,
        "竞品": detected["competitor"],
        "来源平台": platform,
        "抓取策略": strategy,
        "HTTP状态": http_status,
        "重定向": redirected,
        "final_url": final_url,
        "标题获取": "✅" if title else "❌",
        "发布时间获取": "✅" if published_date else "❌",
        "正文获取": "✅" if content_snippet else "❌",
        "正文长度": len(content_snippet) if content_snippet else 0,
        "fetch_status": fetch_status,
        "fetch_error": fetch_error or "",
        "能力等级": cap.automation_level,
        "需要人工补充": "是" if cap.needs_manual else "否",
        "人工补充字段": "、".join(needs_manual_fields) if needs_manual_fields else "—",
        "建议处理方式": cap.suggestion,
        "是否专项处理": "是" if strategy == "github_special" else "否",
        "github_event_type": gh_info.get("github_event_type", ""),
        "repository": gh_info.get("repository_name", ""),
        "docs_changed": "✅" if gh_info.get("docs_changed") else "",
        "capability_change": "✅" if gh_info.get("capability_change") else "",
        "integration_change": "✅" if gh_info.get("integration_change") else "",
        "developer_experience_change": "✅" if gh_info.get("developer_experience_change") else "",
        "change_summary": gh_info.get("change_summary", commits_summary),
        "title": title or "",
        "published_date": published_date or "",
    }

    cap = classify_fetch_result(
        fetch_status=fr.status,
        has_title=bool(fr.title),
        has_description=bool(fr.description),
        has_published_date=bool(fr.published_date),
        source_platform=detected["source_platform"],
    )

    needs_manual_fields = []
    if not fr.title:
        needs_manual_fields.append("标题")
    if not fr.published_date:
        needs_manual_fields.append("发布时间")
    if not fr.description:
        needs_manual_fields.append("摘要")

    return {
        "tested_at": datetime.now(timezone.utc).isoformat()[:19].replace("T", " "),
        "url": url,
        "normalized_url": norm,
        "竞品": detected["competitor"],
        "来源平台": detected["source_platform"],
        "HTTP状态": fr.http_status_code or "",
        "content_type": "",  # fetch_url 未暴露，用 content_source 代替
        "content_source": fr.content_source or "",
        "重定向": "是" if (fr.final_url and fr.final_url != url) else "否",
        "final_url": fr.final_url or url,
        "标题获取": "✅" if fr.title else "❌",
        "发布时间获取": "✅" if fr.published_date else "❌",
        "正文获取": "✅" if fr.content_snippet else "❌",
        "正文长度": len(fr.content_snippet) if fr.content_snippet else 0,
        "fetch_status": fr.status,
        "fetch_error": fr.error or "",
        "能力等级": cap.automation_level,
        "需要人工补充": "是" if cap.needs_manual else "否",
        "人工补充字段": "、".join(needs_manual_fields) if needs_manual_fields else "—",
        "建议处理方式": cap.suggestion,
        # GitHub 专项
        "github_event_type": gh_info.get("github_event_type", ""),
        "repository": gh_info.get("repository_name", ""),
        "docs_changed": "✅" if gh_info.get("docs_changed") else "",
        "capability_change": "✅" if gh_info.get("capability_change") else "",
        "integration_change": "✅" if gh_info.get("integration_change") else "",
        "developer_experience_change": "✅" if gh_info.get("developer_experience_change") else "",
        "change_summary": gh_info.get("change_summary", ""),
        "title": fr.title or "",
        "published_date": fr.published_date or "",
    }


# ── Tab 布局 ────────────────────────────────────────────────
tab1, tab2, tab3, tab4 = st.tabs(["单链接测试", "批量测试", "来源能力总览", "历史测试结果"])


# ══════════════════════════════════════════════════════════════════
# Tab 1：单链接测试
# ══════════════════════════════════════════════════════════════════
with tab1:
    st.subheader("单链接诊断")
    url_input = st.text_input("输入 URL", placeholder="https://exa.ai/blog/...", key="cap_single")

    if st.button("开始测试", key="run_single") and url_input.strip():
        url = url_input.strip()
        if not is_valid_url(url):
            st.error("URL 格式无效")
        else:
            with st.spinner("测试中..."):
                row = _run_single_test(url)

            level = row["能力等级"]
            level_color = {"A": "#1a6b3c", "B": "#e67e22", "C": "#c0392b"}.get(level, "#666")
            strategy_label = {"github_special": "GitHub 专项", "generic_web": "通用网页", "manual_fallback": "人工补充"}.get(row.get("抓取策略",""), row.get("抓取策略",""))
            st.markdown(
                f'能力等级：<span style="background:{level_color};color:#fff;border-radius:4px;'
                f'padding:2px 10px;font-size:14px;font-weight:bold;">级别 {level}</span>'
                f'&nbsp;&nbsp;抓取策略：<b>{strategy_label}</b>',
                unsafe_allow_html=True,
            )

            col1, col2, col3, col4, col5, col6 = st.columns(6)
            col1.metric("竞品", row["竞品"])
            col2.metric("来源平台", row["来源平台"])
            col3.metric("fetch_status", row["fetch_status"])
            col4.metric("标题", row["标题获取"])
            col5.metric("发布时间", row["发布时间获取"])
            col6.metric("专项处理", row.get("是否专项处理", "否"))

            if row["title"]:
                st.info(f"标题：{row['title']}")
            if row["fetch_error"]:
                st.warning(f"错误：{row['fetch_error']}")
            if row["需要人工补充"] == "是":
                st.warning(f"需人工补充：{row['人工补充字段']}")
            st.caption(f"建议：{row['建议处理方式']}")

            if row["github_event_type"]:
                st.markdown("**GitHub 分析**")
                st.caption(
                    f"类型：{row['github_event_type']}  |  "
                    f"仓库：{row['repository']}  |  "
                    f"文档：{row['docs_changed']}  产品能力：{row['capability_change']}  "
                    f"生态集成：{row['integration_change']}  开发者体验：{row['developer_experience_change']}"
                )
                if row["change_summary"]:
                    st.caption(f"变化摘要：{row['change_summary']}")

            if row.get("final_url") and row["final_url"] != url:
                st.caption(f"最终 URL：{row['final_url']}")

            if "cap_history" not in st.session_state:
                st.session_state["cap_history"] = []
            st.session_state["cap_history"].append(row)


# ══════════════════════════════════════════════════════════════════
# Tab 2：批量测试
# ══════════════════════════════════════════════════════════════════
with tab2:
    st.subheader("批量测试")

    preset_data = _load_preset_urls()
    preset_urls = _flatten_preset_urls(preset_data)

    use_preset = st.checkbox(
        f"使用预设测试链接（共 {len(preset_urls)} 条）",
        value=False, key="use_preset",
    )

    if use_preset:
        url_list = preset_urls
        st.caption("预设链接：" + " | ".join(u[:60] for u in url_list[:5])
                   + ("..." if len(url_list) > 5 else ""))
    else:
        bulk_text = st.text_area(
            "每行输入一个 URL", height=200,
            placeholder="https://exa.ai/blog/...\nhttps://github.com/exa-labs/exa-py",
            key="cap_bulk",
        )
        url_list = [l.strip() for l in (bulk_text or "").splitlines() if l.strip()]

    if st.button("开始批量测试", key="run_bulk", type="primary") and url_list:
        progress = st.progress(0)
        results = []
        total = len(url_list)
        for i, url in enumerate(url_list):
            try:
                if is_valid_url(url):
                    row = _run_single_test(url)
                else:
                    row = {
                        "tested_at": datetime.now(timezone.utc).isoformat()[:19].replace("T", " "),
                        "url": url, "fetch_status": "invalid", "fetch_error": "URL格式无效",
                        "竞品": "—", "来源平台": "—", "能力等级": "—", "需要人工补充": "是",
                        "标题获取": "❌", "发布时间获取": "❌", "正文获取": "❌",
                        "正文长度": 0, "建议处理方式": "URL格式无效，请检查后重新输入",
                    }
            except Exception as e:
                row = {
                    "tested_at": datetime.now(timezone.utc).isoformat()[:19].replace("T", " "),
                    "url": url, "fetch_status": "error", "fetch_error": str(e)[:80],
                    "竞品": "—", "来源平台": "—", "能力等级": "—", "需要人工补充": "是",
                    "标题获取": "❌", "发布时间获取": "❌", "正文获取": "❌",
                    "正文长度": 0, "建议处理方式": "发生未知错误",
                }
            results.append(row)
            progress.progress((i + 1) / total)

        progress.empty()
        st.session_state["bulk_test_results"] = results

        if "cap_history" not in st.session_state:
            st.session_state["cap_history"] = []
        st.session_state["cap_history"].extend(results)

        st.success(f"测试完成，共 {total} 条")

    if "bulk_test_results" in st.session_state:
        results = st.session_state["bulk_test_results"]
        display_cols = ["url", "竞品", "来源平台", "fetch_status", "能力等级",
                        "标题获取", "发布时间获取", "正文获取", "fetch_error", "需要人工补充"]
        df = pd.DataFrame(results)
        show_df = df[[c for c in display_cols if c in df.columns]]
        st.dataframe(show_df, use_container_width=True, height=400)

        # 统计
        level_counts = df["能力等级"].value_counts().to_dict() if "能力等级" in df.columns else {}
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("A级（稳定抓取）", level_counts.get("A", 0))
        c2.metric("B级（部分抓取）", level_counts.get("B", 0))
        c3.metric("C级（人工补充）", level_counts.get("C", 0))
        c4.metric("需人工补充", sum(1 for r in results if r.get("需要人工补充") == "是"))

        # 导出
        buf = io.BytesIO()
        with pd.ExcelWriter(buf, engine="openpyxl") as writer:
            df.to_excel(writer, index=False, sheet_name="能力测试结果")
        st.download_button(
            "📥 导出测试结果 Excel",
            data=buf.getvalue(),
            file_name=f"source_capability_test_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )

        # 追加保存到 data/
        _RESULT_FILE = Path(__file__).parent.parent / "data" / "source_capability_results.xlsx"
        try:
            if _RESULT_FILE.exists():
                existing = pd.read_excel(_RESULT_FILE)
                combined = pd.concat([existing, df], ignore_index=True)
            else:
                combined = df
            with pd.ExcelWriter(str(_RESULT_FILE), engine="openpyxl") as w:
                combined.to_excel(w, index=False, sheet_name="能力测试历史")
        except Exception:
            pass


# ══════════════════════════════════════════════════════════════════
# Tab 3：来源能力总览
# ══════════════════════════════════════════════════════════════════
with tab3:
    st.subheader("来源能力配置总览")
    st.caption("基于 config/source_capabilities.yaml，可手动编辑配置文件调整等级。")

    all_caps = list_all_capabilities()
    rows = []
    for platform, cfg in all_caps.items():
        lvl = cfg["automation_level"]
        rows.append({
            "来源平台": platform,
            "能力等级": lvl,
            "默认处理方式": cfg["default_action"],
            "说明": cfg.get("description", ""),
        })
    df_caps = pd.DataFrame(rows)

    LEVEL_STYLE = {"A": "background-color:#d4edda", "B": "background-color:#fff3cd",
                   "C": "background-color:#f8d7da"}

    def _style_row(row):
        lvl = row.get("能力等级", "")
        style = LEVEL_STYLE.get(lvl, "")
        return [style] * len(row)

    st.dataframe(df_caps, use_container_width=True, hide_index=True)

    st.markdown("""
**等级说明：**
- **A** — 可稳定自动抓取，标题和内容均可获取
- **B** — 可部分自动抓取，需要人工补充部分字段（如发布时间/摘要）
- **C** — 主要依赖人工补充（403/登录限制/动态渲染）
""")


# ══════════════════════════════════════════════════════════════════
# Tab 4：历史测试结果
# ══════════════════════════════════════════════════════════════════
with tab4:
    st.subheader("本次会话测试历史")
    history = st.session_state.get("cap_history", [])
    if not history:
        st.info("本次会话暂无测试记录，请先在其他 Tab 执行测试。")
    else:
        df_hist = pd.DataFrame(history)
        st.caption(f"共 {len(df_hist)} 条测试记录")
        display_cols_h = ["tested_at", "url", "竞品", "来源平台", "fetch_status", "能力等级", "标题获取", "需要人工补充"]
        st.dataframe(df_hist[[c for c in display_cols_h if c in df_hist.columns]],
                     use_container_width=True, height=400)

    # 读取历史持久化结果
    _RESULT_FILE2 = Path(__file__).parent.parent / "data" / "source_capability_results.xlsx"
    if _RESULT_FILE2.exists():
        st.markdown("---")
        st.markdown("**历史持久化测试记录**（data/source_capability_results.xlsx）")
        try:
            df_saved = pd.read_excel(str(_RESULT_FILE2))
            st.caption(f"共 {len(df_saved)} 条历史记录")
            st.dataframe(df_saved[["tested_at", "url", "竞品", "来源平台", "fetch_status", "能力等级"]
                                   if all(c in df_saved.columns for c in ["tested_at", "url", "竞品", "来源平台", "fetch_status", "能力等级"])
                                   else list(df_saved.columns)[:6]],
                         use_container_width=True, height=300)
        except Exception as e:
            st.warning(f"读取历史文件失败：{e}")
