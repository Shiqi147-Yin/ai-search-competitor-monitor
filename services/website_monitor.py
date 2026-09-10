"""官网主动巡检服务
不依赖 Querit API，主动访问官方 Blog / Docs / Integration 入口，
提取时间窗口内的具体更新。
复用已有的 drilldown_blog() 和 drilldown_docs() 逻辑。
"""
from dataclasses import dataclass, field
from typing import Optional

from services.source_drilldown import drilldown_blog, drilldown_docs
from services.docs_page_role_classifier import classify_docs_page_role
from services.docs_change_detector import detect_change


@dataclass
class WebsiteUpdateItem:
    competitor: str = ""
    source_type: str = ""          # blog / docs / integration
    source_url: str = ""
    title: str = ""
    published_at: str = ""         # Blog 专用：文章发布时间
    updated_at: str = ""           # Docs 专用：sitemap lastmod
    summary: str = ""
    content_snippet: str = ""
    page_role: str = "generic"
    is_generic_page: bool = True
    is_entry_page: bool = False
    update_status: str = ""        # new_page/substantive_update/metadata_only/first_seen/unchanged
    discovery_method: str = "official_direct"
    import_eligible: bool = True
    within_window: bool = False


def monitor_blog(
    competitor: str,
    entry_urls: list[str],
    window_start: str,
    window_end: str,
) -> list[WebsiteUpdateItem]:
    """主动巡检 Blog，返回时间窗口内的具体文章（不含入口页）。
    网络错误向上抛出，由 run_website_monitor 捕获并记录。
    """
    items: list[WebsiteUpdateItem] = []
    for entry_url in entry_urls:
        drill = drilldown_blog(entry_url, window_start, window_end)
        for discovered in drill.discovered_items:
            if discovered.is_entry_page:
                continue  # 入口页不作为动态
            items.append(WebsiteUpdateItem(
                competitor=competitor,
                source_type="blog",
                source_url=discovered.source_url,
                title=discovered.title,
                published_at=discovered.published_date,
                updated_at="",
                page_role="detail_article",
                is_generic_page=False,
                is_entry_page=False,
                update_status="new_page",
                discovery_method="official_blog_monitor",
                import_eligible=discovered.import_eligible,
                within_window=discovered.within_window,
            ))
    return items


def monitor_docs(
    competitor: str,
    entry_urls: list[str],
    sitemap_urls: list[str],
    window_start: str,
    window_end: str,
    source_type: str = "docs",
    db_path=None,
) -> list[WebsiteUpdateItem]:
    """主动巡检 Docs / Integration，返回候选更新页面。
    lastmod 写入 updated_at，严禁写入 published_at。
    """
    items: list[WebsiteUpdateItem] = []
    seen: set[str] = set()

    # 优先通过 sitemap 驱动（已有 drilldown_docs 实现）
    target_urls = sitemap_urls if sitemap_urls else entry_urls
    for entry_url in target_urls:
        try:
            drill = drilldown_docs(entry_url, window_start, window_end)
            for discovered in drill.discovered_items:
                if discovered.source_url in seen:
                    continue
                seen.add(discovered.source_url)

                role, is_generic = classify_docs_page_role(discovered.source_url, discovered.title)

                # 调用变化检测（首次运行无历史快照时为 new_page）
                change_result = detect_change(
                    url=discovered.source_url,
                    raw_html="",  # 当前版本不预抓取正文，依赖 sitemap 作为候选信号
                    competitor=competitor,
                    source_type=source_type,
                    title=discovered.title,
                    lastmod=discovered.updated_at,
                    db_path=db_path,
                )

                # 状态判定：仅 sitemap_lastmod 不足以证明实质更新，标记为待确认
                _update_status = change_result.update_status
                if (competitor == "Brave"
                        and discovered.discovery_method == "sitemap_lastmod"
                        and _update_status in ("new_page", "first_seen", "unknown", "")):
                    _update_status = "docs_pending_confirmation"

                # sitemap 驱动时：lastmod → updated_at，不写 published_at
                items.append(WebsiteUpdateItem(
                    competitor=competitor,
                    source_type=source_type,
                    source_url=discovered.source_url,
                    title=discovered.title,
                    published_at="",           # Docs 不写 published_at
                    updated_at=discovered.updated_at,
                    page_role=role,
                    is_generic_page=is_generic,
                    is_entry_page=False,
                    update_status=_update_status,
                    discovery_method="official_docs_monitor",
                    import_eligible=discovered.import_eligible and not is_generic,
                    within_window=discovered.within_window,
                ))
        except Exception as e:
            pass  # 单入口失败不中断
    return items


def run_website_monitor(
    competitor: str,
    config: dict,
    window_start: str,
    window_end: str,
    source_types: list[str],
    db_path=None,
) -> dict:
    """执行官网主动巡检。

    Args:
        competitor:   竞品名称（如 "Tavily"）
        config:       official_monitoring_sources.yaml 中对应竞品的 website 配置
        window_start: 时间窗口开始（ISO 8601）
        window_end:   时间窗口结束（ISO 8601）
        source_types: 要巡检的来源类型列表，支持 all/blog/docs/integrations
        db_path:      可选：测试用独立 DB

    Returns:
        {
            "blog":        list[WebsiteUpdateItem],
            "docs":        list[WebsiteUpdateItem],
            "integrations": list[WebsiteUpdateItem],
            "errors":      list[dict],
        }
    """
    all_types = set(source_types)
    run_all = "all" in all_types

    result: dict = {
        "blog": [],
        "docs": [],
        "integrations": [],
        "errors": [],
    }

    # Blog
    if run_all or "blog" in all_types:
        blog_urls = config.get("blog", [])
        if blog_urls:
            try:
                result["blog"] = monitor_blog(competitor, blog_urls, window_start, window_end)
            except Exception as e:
                result["errors"].append({
                    "source_type": "blog",
                    "error": f"{type(e).__name__}: {str(e)[:120]}",
                })

    # Docs
    if run_all or "docs" in all_types:
        docs_urls = config.get("docs", [])
        # 优先含 "docs." 的 sitemap；若无则使用所有 sitemap（Brave 用 brave.com/en/sitemap.xml）
        all_sitemaps = config.get("sitemap", [])
        docs_sitemaps = [u for u in all_sitemaps if "docs." in u] or all_sitemaps
        if docs_urls or docs_sitemaps:
            try:
                result["docs"] = monitor_docs(
                    competitor, docs_urls, docs_sitemaps,
                    window_start, window_end,
                    source_type="docs", db_path=db_path,
                )
            except Exception as e:
                result["errors"].append({
                    "source_type": "docs",
                    "error": f"{type(e).__name__}: {str(e)[:120]}",
                })

    # Integrations
    if run_all or "integrations" in all_types:
        int_urls = config.get("integrations", [])
        # integration 页面一般在 docs sitemap 内，使用 docs sitemap 驱动
        sitemap_urls = [u for u in config.get("sitemap", []) if "docs." in u]
        if int_urls:
            try:
                result["integrations"] = monitor_docs(
                    competitor, int_urls, sitemap_urls,
                    window_start, window_end,
                    source_type="integration", db_path=db_path,
                )
            except Exception as e:
                result["errors"].append({
                    "source_type": "integrations",
                    "error": f"{type(e).__name__}: {str(e)[:120]}",
                })

    return result
