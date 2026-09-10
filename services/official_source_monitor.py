"""统一巡检入口（Orchestrator）
读取官方来源配置 → website monitor → github monitor →
Docs 变化判断 → GitHub commit 聚合 → 归一化 → 去重 → 可选 Querit 补充 → 返回统一结果
"""
import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

try:
    import yaml
    _HAS_YAML = True
except ImportError:
    _HAS_YAML = False

from services.website_monitor import run_website_monitor
from services.github_monitor import run_github_monitor
from services.github_event_aggregator import aggregate_commits
from services.official_update_normalizer import normalize_all, OfficialUpdateItem
from services.monitoring_result_merger import merge_results

_DEFAULT_CONFIG_PATH = Path(__file__).parent.parent / "config" / "official_monitoring_sources.yaml"


@dataclass
class OfficialMonitorResult:
    competitor: str = ""
    window_start: str = ""
    window_end: str = ""
    website_results: list = field(default_factory=list)    # list[OfficialUpdateItem] - Blog + Docs
    github_results: list = field(default_factory=list)     # list[OfficialUpdateItem] - primary commit groups + releases
    github_diagnostic_results: list = field(default_factory=list)  # maintenance/internal commits
    querit_supplement_results: list = field(default_factory=list)
    errors: list = field(default_factory=list)
    source_stats: dict = field(default_factory=dict)
    started_at: str = ""
    completed_at: str = ""


def load_monitoring_config(config_path=None) -> dict:
    """读取 official_monitoring_sources.yaml，返回完整配置字典。"""
    path = Path(config_path) if config_path else _DEFAULT_CONFIG_PATH
    if not path.exists():
        raise FileNotFoundError(f"官方来源配置文件不存在: {path}")
    if not _HAS_YAML:
        raise ImportError("pyyaml 未安装，请执行 pip install pyyaml")
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def run_official_monitor(
    competitor: str,
    window_start: str,
    window_end: str,
    source_types: list,
    enable_querit_supplement: bool = False,
    config_path=None,
    db_path=None,
) -> OfficialMonitorResult:
    """执行官方来源主动巡检。

    主流程：
    1. 读取配置
    2. website_monitor（Blog + Docs + Integrations）
    3. github_monitor（commits + releases）
    4. GitHub commit 聚合
    5. 归一化所有来源 → OfficialUpdateItem
    6. 去重（按 source_url）
    7. 可选 Querit 补充（默认关闭）
    8. 返回 OfficialMonitorResult

    Args:
        competitor:               竞品名称（如 "Tavily"）
        window_start:             ISO 8601（如 "2026-07-08"）
        window_end:               ISO 8601（如 "2026-07-17"）
        source_types:             ["all"] 或 ["blog","docs","integrations","github"] 组合
        enable_querit_supplement: 默认 False
        config_path:              可选：覆盖默认配置路径
        db_path:                  可选：测试用独立 DB

    Returns:
        OfficialMonitorResult
    """
    result = OfficialMonitorResult(
        competitor=competitor,
        window_start=window_start,
        window_end=window_end,
        started_at=_now_iso(),
    )

    # ── 1. 读取配置 ──────────────────────────────────────────────
    try:
        full_config = load_monitoring_config(config_path)
    except Exception as e:
        result.errors.append({"source_type": "config", "error": str(e)})
        result.completed_at = _now_iso()
        return result

    comp_config = full_config.get(competitor, {})
    if not comp_config:
        result.errors.append({
            "source_type": "config",
            "error": f"配置中未找到竞品 '{competitor}'，可用: {list(full_config.keys())}",
        })
        result.completed_at = _now_iso()
        return result

    website_config = comp_config.get("website", {})
    github_config = comp_config.get("github", {})

    run_all = "all" in source_types
    run_website = run_all or any(t in source_types for t in ("blog", "docs", "integrations"))
    run_github = run_all or "github" in source_types

    # ── 2. 官网巡检 ──────────────────────────────────────────────
    blog_items, docs_items, integration_items = [], [], []
    if run_website and website_config:
        try:
            web_result = run_website_monitor(
                competitor, website_config, window_start, window_end,
                source_types=source_types, db_path=db_path,
            )
            blog_items = web_result.get("blog", [])
            docs_items = web_result.get("docs", [])
            integration_items = web_result.get("integrations", [])
            result.errors.extend(web_result.get("errors", []))

            result.source_stats["blog"] = {
                "found": len(blog_items),
                "blog_all_in_window": sum(1 for i in blog_items if i.within_window),
                # 兼容旧字段名（其他竞品仍使用 in_window）
                "in_window": sum(1 for i in blog_items if i.within_window),
            }

            # docs_status：标注 Docs 访问结果
            _docs_errors = [e for e in web_result.get("errors", [])
                            if e.get("source_type") in ("docs", "website")]
            _docs_entry_url = (website_config.get("docs") or [None])[0]
            _docs_sitemap_urls = website_config.get("sitemap", [])
            # sitemap 过滤：website_monitor 仅传给 monitor_docs 含 "docs." 的 sitemap
            # Brave 的 sitemap 是 brave.com/en/sitemap.xml（不含 "docs."），实际由 entry URL 触发
            _docs_sitemap_used = [u for u in _docs_sitemap_urls if "docs." in u] or _docs_sitemap_urls

            # 构建 docs_status
            if docs_items:
                _docs_status = "ok"
            elif any("403" in str(e.get("error", "")) for e in _docs_errors):
                _docs_status = "blocked_403"
            elif _docs_errors:
                _docs_status = "unavailable"
            elif not _docs_entry_url and not _docs_sitemap_used:
                _docs_status = "not_configured"
            else:
                _docs_status = "no_pages_found"

            # docs_empty_reason（仅 docs_items==0 时有意义）
            if not docs_items:
                if not _docs_entry_url:
                    _docs_empty_reason = "config_missing"
                elif any("403" in str(e.get("error", "")) for e in _docs_errors):
                    _docs_empty_reason = "entry_blocked_403"
                elif _docs_errors:
                    _docs_empty_reason = "fetch_error"
                else:
                    # sitemap 成功但无窗口内更新
                    _docs_empty_reason = "no_search_pages_in_window"
            else:
                _docs_empty_reason = ""

            result.source_stats["docs"] = {
                "found": len(docs_items),
                "in_window": sum(1 for i in docs_items if i.within_window),
                "docs_status": _docs_status,
                "docs_entry_url": _docs_entry_url or "",
                "docs_sitemap_url": _docs_sitemap_used[0] if _docs_sitemap_used else "",
                "docs_empty_reason": _docs_empty_reason,
            }
            result.source_stats["integrations"] = {
                "found": len(integration_items),
                "in_window": sum(1 for i in integration_items if i.within_window),
            }
        except Exception as e:
            result.errors.append({"source_type": "website", "error": f"{type(e).__name__}: {str(e)[:200]}"})

    # ── 3. GitHub 巡检 ────────────────────────────────────────────
    github_events_normalized, github_releases_normalized = [], []
    github_diagnostic_events = []
    if run_github and github_config:
        try:
            gh_result = run_github_monitor(competitor, github_config, window_start, window_end)
            raw_commits = gh_result.get("commits", [])
            raw_releases = gh_result.get("releases", [])
            result.errors.extend(gh_result.get("errors", []))

            # 4. commit 聚合
            aggregated_events = aggregate_commits(raw_commits)

            # 4b. 相关性过滤（读取竞品关键词配置）
            from services.github_relevance_scorer import filter_events_by_relevance
            comp_kw = comp_config.get("relevance_keywords", None)
            primary_events, diagnostic_events = filter_events_by_relevance(
                aggregated_events, config_keywords=comp_kw
            )

            # 4c. Release 去重：同一 repo+version 只保留一条
            seen_releases: set[str] = set()
            deduped_releases = []
            for rel in raw_releases:
                dedup_key = f"{rel.repository}:{rel.version}"
                if dedup_key not in seen_releases:
                    seen_releases.add(dedup_key)
                    deduped_releases.append(rel)

            _github_status = "ok" if raw_commits else "success_no_updates"
            result.source_stats["github_commits"] = {
                "found": len(raw_commits),
                "in_window": len(raw_commits),
                "aggregated_events": len(aggregated_events),
                "primary_events": len(primary_events),
                "diagnostic_events": len(diagnostic_events),
                "github_status": _github_status,
            }
            result.source_stats["github_releases"] = {
                "found": len(raw_releases),
                "in_window": len(raw_releases),
                "deduped": len(deduped_releases),
            }

            # 5. 归一化 GitHub 结果
            from services.official_update_normalizer import normalize_github_event, normalize_github_release
            from services.github_final_events import merge_releases_with_events

            # GitHub Event Synthesis mode（默认 deterministic，可选 mock / llm）
            import os
            synthesis_mode = os.environ.get("GITHUB_EVENT_SYNTHESIS_MODE", "deterministic")

            if synthesis_mode in ("mock", "llm"):
                # LLM synthesizer 路径（mock 或真实 LLM）
                from services.github_event_synthesizer import (
                    synthesize_github_events, GithubBusinessEvent, SynthesisResult,
                )
                synthesis_result: SynthesisResult = synthesize_github_events(
                    competitor=competitor,
                    raw_commits=raw_commits,
                    raw_releases=deduped_releases,
                    window_start=window_start,
                    window_end=window_end,
                    competitor_context=f"AI Search API competitor: {competitor}",
                    provider_name=synthesis_mode,
                    config_keywords=comp_kw,
                )

                def _be_to_item(be: GithubBusinessEvent):
                    from services.official_update_normalizer import OfficialUpdateItem
                    item = OfficialUpdateItem(
                        competitor=be.competitor or competitor,
                        update_title=be.event_title,
                        update_date=be.event_date,
                        source_channel="github_commit_group" if not be.is_release else "github_release",
                        content_type="commit_group" if not be.is_release else "release",
                        source_url=be.evidence_urls[0] if be.evidence_urls else "",
                        summary=be.summary,
                        key_points=be.key_changes,
                        category=be.event_type,
                        importance=be.importance,
                        discovery_method="official_direct",
                        import_eligible=True,
                        evidence_urls=be.evidence_urls,
                        within_window=True,
                    )
                    item.synthesis_method = be.synthesis_method
                    item.github_relevance = be.event_type
                    item.github_relevance_score = be.confidence
                    item.evidence_count = be.evidence_count
                    item.github_business_event = be
                    return item

                final_github_events = [_be_to_item(be) for be in synthesis_result.events]
                for item in final_github_events:
                    if not item.competitor:
                        item.competitor = competitor

                result.source_stats["github_commits"]["synthesis_mode"] = synthesis_mode
                result.source_stats["github_commits"]["synthesis_status"] = synthesis_result.synthesis_status
                result.source_stats["github_commits"]["final_events"] = len(final_github_events)
                result.source_stats["github_releases"]["merged_into_final"] = len(deduped_releases)

            else:
                # ── 默认：deterministic 路径 ────────────────────────────
                github_events_normalized_pre = [normalize_github_event(e, competitor) for e in primary_events]
                for item, event in zip(github_events_normalized_pre, primary_events):
                    item.github_relevance = getattr(event, "github_relevance", "")
                    item.github_relevance_score = getattr(event, "github_relevance_score", 0.0)
                    item.github_relevance_reason = getattr(event, "github_relevance_reason", "")
                    item.is_release_or_version_bump = getattr(event, "is_release_or_version_bump", False)

                final_github_events, _ = merge_releases_with_events(
                    deduped_releases, github_events_normalized_pre
                )
                for item in final_github_events:
                    if not item.competitor:
                        item.competitor = competitor

                result.source_stats["github_commits"]["synthesis_mode"] = "deterministic"
                result.source_stats["github_commits"]["final_events"] = len(final_github_events)
                result.source_stats["github_releases"]["merged_into_final"] = len(deduped_releases)

            github_events_normalized = final_github_events
            github_releases_normalized = []
            github_diagnostic_events = [normalize_github_event(e, competitor) for e in diagnostic_events]

        except Exception as e:
            result.errors.append({"source_type": "github", "error": f"{type(e).__name__}: {str(e)[:200]}"})
            # 保证 github_commits 统计项始终存在（便于诊断）
            if "github_commits" not in result.source_stats:
                result.source_stats["github_commits"] = {
                    "found": 0, "in_window": 0, "aggregated_events": 0,
                    "primary_events": 0, "diagnostic_events": 0,
                    "github_status": "error",
                }

    # ── 5. 归一化官网结果 ─────────────────────────────────────────
    website_normalized = normalize_all(
        competitor=competitor,
        blog_items=blog_items,
        docs_items=docs_items,
        integration_items=integration_items,
    )

    # ── 5b. Brave Search relevance filter（只对 Brave 生效）───────
    brave_search_filter_stats = {}
    if competitor == "Brave":
        from services.brave_search_relevance import filter_brave_items_by_search_relevance
        website_normalized, _filtered_out, brave_search_filter_stats = \
            filter_brave_items_by_search_relevance(website_normalized)
        result.source_stats["brave_search_filter"] = brave_search_filter_stats

        # Blog 漏斗（Brave 专属）：只统计 Blog 来源，不包含 Docs/Integration
        _search_blog = [i for i in website_normalized
                        if getattr(i, "source_channel", "") == "website_blog"]
        _in_window = [i for i in _search_blog if getattr(i, "within_window", False) is True]
        _outside_window = [i for i in _search_blog if getattr(i, "within_window", False) is False]
        _invalid_date = [i for i in _search_blog
                         if getattr(i, "within_window", None) is None]
        # brave_search_filter.scanned 包含 Blog+Docs，需分开统计
        _blog_before_filter = len(blog_items)  # 原始 Blog 数量（过滤前）
        _docs_before_filter = len(docs_items)   # 原始 Docs 数量（过滤前）
        _blog_pre_filter_scanned = brave_search_filter_stats.get("scanned", 0) - _docs_before_filter
        _blog_search_related = len(_search_blog)
        _blog_non_search = _blog_before_filter - _blog_search_related
        result.source_stats["blog_funnel"] = {
            "blog_discovered": _blog_before_filter,
            "blog_search_related": _blog_search_related,
            "blog_non_search_filtered": _blog_non_search,
            "blog_in_window": len(_in_window),
            "blog_outside_window": len(_outside_window),
            "blog_invalid_date": len(_invalid_date),
        }

        # Docs 漏斗（Brave 专属）：只统计 Docs/Integration 来源
        _search_docs = [i for i in website_normalized
                        if getattr(i, "source_channel", "") in ("website_docs", "website_integration")]
        _docs_in_window = [i for i in _search_docs if getattr(i, "within_window", False) is True]
        _docs_outer = [i for i in _search_docs if getattr(i, "within_window", False) is False]
        _docs_no_date = [i for i in _search_docs if getattr(i, "within_window", None) is None]
        _docs_confirmed = [i for i in _docs_in_window
                           if getattr(i, "update_status", "") not in ("docs_pending_confirmation", "first_seen", "")]
        _docs_pending = [i for i in _docs_in_window
                         if getattr(i, "update_status", "") in ("docs_pending_confirmation", "first_seen", "")]
        _docs_search_related = len(_search_docs)
        _docs_non_search = _docs_before_filter - _docs_search_related
        result.source_stats["docs_funnel"] = {
            "docs_discovered": _docs_before_filter,
            "docs_search_related": _docs_search_related,
            "docs_non_search_filtered": _docs_non_search,
            "docs_in_window": len(_docs_in_window),
            "docs_confirmed": len(_docs_confirmed),
            "docs_pending": len(_docs_pending),
            "docs_outside_window": len(_docs_outer),
            "docs_date_unknown": len(_docs_no_date),
            "docs_date_source": "sitemap_lastmod",
        }


    # ── 6. 去重（按 source_url）──────────────────────────────────
    seen_urls: set[str] = set()
    deduped_website: list[OfficialUpdateItem] = []
    for item in website_normalized:
        key = item.source_url.strip().rstrip("/").lower() if item.source_url else ""
        if key and key in seen_urls:
            continue
        if key:
            seen_urls.add(key)
        deduped_website.append(item)

    deduped_github: list[OfficialUpdateItem] = []
    for item in github_events_normalized + github_releases_normalized:
        key = item.source_url.strip().rstrip("/").lower() if item.source_url else ""
        if key and key in seen_urls:
            continue
        if key:
            seen_urls.add(key)
        deduped_github.append(item)

    result.website_results = deduped_website
    result.github_results = deduped_github
    result.github_diagnostic_results = github_diagnostic_events

    # ── 7. 可选 Querit 补充 ──────────────────────────────────────
    if enable_querit_supplement:
        try:
            querit_items = _run_querit_supplement(competitor, window_start, window_end)
            all_official = deduped_website + deduped_github
            merge = merge_results(all_official, querit_items)
            result.website_results = [i for i in merge.official_items
                                       if i.source_channel in ("website_blog", "website_docs", "website_integration")]
            result.github_results = [i for i in merge.official_items
                                      if i.source_channel in ("github_commit_group", "github_release")]
            result.querit_supplement_results = merge.querit_supplement
            result.source_stats["querit_supplement"] = {
                "querit_found": len(querit_items),
                "querit_new": len(merge.querit_supplement),
                "querit_duplicate": merge.merged_count,
            }
        except Exception as e:
            result.errors.append({"source_type": "querit_supplement", "error": str(e)[:200]})

    result.completed_at = _now_iso()
    return result


_SUPPLEMENT_QUERIES = {
    "Tavily": [
        "Tavily Search API latest updates",
        "Tavily integration agent MCP",
        "Tavily Search API release",
    ],
    "Exa": [
        "Exa Search API latest updates",
        "Exa integration agent MCP",
        "Exa API SDK release",
    ],
    "Brave": [
        "Brave Search API latest updates",
        "Brave Search API integration",
        "Brave Search API release",
    ],
}


def _build_supplement_queries(competitor: str) -> list[str]:
    """返回竞品专属 Querit 补充 Query。"""
    return _SUPPLEMENT_QUERIES.get(competitor, [
        f"{competitor} API latest updates",
        f"{competitor} integration agent",
        f"{competitor} release",
    ])


def _run_querit_supplement(competitor: str, window_start: str, window_end: str) -> list[OfficialUpdateItem]:
    """调用 Querit Search API 补充发现，返回归一化的 OfficialUpdateItem 列表。
    仅使用真实 API（临时覆盖 QUERIT_MOCK_MODE=false），失败返回 0 条，不自动补 Mock。
    """
    import os as _os
    from services.querit_client import search, SearchRunResult
    from services.source_drilldown import _within_window

    # 强制禁用 Mock 模式（supplement 只从真实 API 获取）
    _old_mock = _os.environ.get("QUERIT_MOCK_MODE")
    _os.environ["QUERIT_MOCK_MODE"] = "false"

    try:
        items: list[OfficialUpdateItem] = []
        seen_urls: set[str] = set()
        queries = _build_supplement_queries(competitor)

        for query in queries:
            try:
                run: SearchRunResult = search(query, num_results=5)
                if not run.success:
                    continue

                for sr in run.results:
                    url = (sr.url or "").strip()
                    if not url or url in seen_urls:
                        continue
                    seen_urls.add(url)

                    # ── Competitor relevance filter ────────────────────
                    title_summary = f"{(sr.title or '').lower()} {(sr.summary or '').lower()}"
                    competitor_lower = competitor.lower()
                    # Skip results clearly about other AI Search competitors
                    other_competitors = [
                        c for c in ("Exa", "Brave", "Kagi", "You.com", "Perplexity", "Andi")
                        if c.lower() != competitor_lower
                    ]
                    mentions_other = any(
                        oc.lower() in title_summary for oc in other_competitors
                        if len(oc) >= 3  # skip 2-letter noise
                    )
                    mentions_target = competitor_lower in title_summary or competitor_lower in url.lower()
                    if mentions_other and not mentions_target:
                        continue  # 纯竞品内容，跳过

                    # ── 日期窗口判断 ────────────────────────────────────
                    pub_date = sr.published_date or ""
                    in_win = bool(_within_window(pub_date, window_start, window_end) if pub_date else False)

                    # ── 官方域名判断 ────────────────────────────────────
                    official_domains = {
                        "Tavily": ["tavily.com", "docs.tavily.com"],
                        "Exa": ["exa.ai", "docs.exa.ai"],
                        "Brave": ["brave.com", "api.search.brave.com"],
                    }
                    domain_list = official_domains.get(competitor, [])
                    is_official = any(d in url.lower() for d in domain_list)

                    item = OfficialUpdateItem(
                        competitor=competitor,
                        update_title=sr.title or url,
                        update_date=pub_date,
                        source_channel="querit_supplement",
                        content_type="querit_supplement",
                        source_url=url,
                        official_source=False,
                        published_at=pub_date,
                        update_status="",
                        summary=sr.summary or (sr.content[:200] if sr.content else ""),
                        discovery_method="querit_supplement",
                        import_eligible=True,
                        within_window=in_win,
                        matched_competitor=competitor,
                        is_official_domain=is_official,
                        duplicate_of_official="",
                        supplement_relevance="medium" if is_official else "low",
                        querit_relevance="supplement",
                    )
                    items.append(item)
            except Exception:
                pass  # 单个 query 失败不影响整体

        return items
    finally:
        # 恢复原始 Mock 设置
        if _old_mock is not None:
            _os.environ["QUERIT_MOCK_MODE"] = _old_mock
        else:
            _os.environ.pop("QUERIT_MOCK_MODE", None)
