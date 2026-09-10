"""页面类型识别服务
根据 URL 路径、域名、标题、source_platform 等字段识别页面类型。
"""
from urllib.parse import urlparse
import re


# 所有已知页面类型
PAGE_TYPES = [
    "detail_article",       # 具体博客/新闻文章
    "blog_index",           # 博客列表/首页
    "docs_detail",          # 具体文档页面
    "docs_index",           # 文档入口/首页
    "github_repository",    # GitHub 仓库首页
    "github_organization",  # GitHub 组织页
    "github_commit",        # 单个 commit
    "github_release",       # release/tag
    "github_commits_list",  # commits 列表
    "event_detail",         # 具体活动详情
    "event_index",          # 活动列表
    "social_post",          # X / LinkedIn 帖子
    "homepage",             # 域名首页
    "aggregator",           # 第三方聚合页
    "unknown",
]

# 不可直接导入的入口页类型
ENTRY_PAGE_TYPES = {
    "homepage",
    "blog_index",
    "docs_index",
    "github_organization",
    "github_repository",
    "event_index",
    "aggregator",
}

# 允许导入的具体内容页
IMPORTABLE_PAGE_TYPES = {
    "detail_article",
    "docs_detail",
    "github_commit",
    "github_release",
    "github_commits_list",
    "event_detail",
    "social_post",
}

_LOW_VALUE_DOMAINS = {
    "advfn.com", "sacra.com", "delv.tools", "mcpshowcase.com",
    "thecompaniesapi.com", "apify.com", "stockanalysis.com",
}


def classify_page_type(
    url: str,
    title: str = "",
    source_platform: str = "",
) -> str:
    """识别 URL 对应的页面类型。"""
    if not url:
        return "unknown"

    try:
        parsed = urlparse(url)
    except Exception:
        return "unknown"

    netloc = parsed.netloc.lower().lstrip("www.")
    path = parsed.path.rstrip("/").lower()
    parts = [p for p in path.split("/") if p]

    # ── 聚合页 ──────────────────────────────────────────────
    if any(d in netloc for d in _LOW_VALUE_DOMAINS):
        return "aggregator"

    # ── 社交媒体帖子 ────────────────────────────────────────
    if netloc in ("x.com", "twitter.com"):
        # /username/status/id → 帖子
        if "status" in parts:
            return "social_post"
        return "homepage"

    if "linkedin.com" in netloc:
        if "posts" in path or "activity" in path or "pulse" in path:
            return "social_post"
        return "homepage"

    # ── GitHub ─────────────────────────────────────────────
    if "github.com" in netloc:
        if len(parts) == 0:
            return "homepage"
        if len(parts) == 1:
            return "github_organization"
        if len(parts) == 2:
            return "github_repository"
        if len(parts) >= 3:
            sub = parts[2]
            if sub == "commit" and len(parts) >= 4:
                return "github_commit"
            if sub in ("releases", "tags"):
                return "github_release"
            if sub == "commits":
                return "github_commits_list"
            if sub in ("blob", "tree"):
                return "docs_detail"
        return "github_repository"

    # ── Event 平台 ─────────────────────────────────────────
    if netloc in ("luma.com", "lu.ma"):
        if len(parts) == 0:
            return "event_index"
        # luma.com/{slug} 是具体活动
        if len(parts) == 1:
            return "event_detail"
        if "event" in parts or "events" in parts:
            return "event_index"
        return "event_detail"

    # ── 文档站 ─────────────────────────────────────────────
    if netloc.startswith("docs."):
        if len(parts) == 0:
            return "docs_index"
        # 路径较深的具体页面
        if len(parts) >= 2:
            return "docs_detail"
        return "docs_index"

    # ── 博客 ────────────────────────────────────────────────
    if "/blog" in path:
        # /blog 且无更深路径 → 列表页
        if path == "/blog" or path.endswith("/blog"):
            return "blog_index"
        # /blog/{slug} → 具体文章
        blog_idx = parts.index("blog") if "blog" in parts else -1
        if blog_idx >= 0 and len(parts) > blog_idx + 1:
            return "detail_article"
        return "blog_index"

    # ── 首页 ────────────────────────────────────────────────
    if len(parts) == 0:
        return "homepage"

    # ── 普通内容页兜底 ─────────────────────────────────────
    # 路径较深，有 slug 特征 → 视为具体文章
    if len(parts) >= 2:
        return "detail_article"

    return "unknown"


def is_entry_page(page_type: str) -> bool:
    return page_type in ENTRY_PAGE_TYPES


def is_import_eligible(page_type: str) -> bool:
    return page_type in IMPORTABLE_PAGE_TYPES


def enrich_with_page_type(rec: dict) -> dict:
    """为记录字典补充页面类型字段。"""
    url = rec.get("source_url") or rec.get("url") or ""
    title = rec.get("title") or ""
    platform = rec.get("source_platform") or ""
    pt = classify_page_type(url, title, platform)
    rec["page_type"] = pt
    rec["is_entry_page"] = is_entry_page(pt)
    rec["import_eligible"] = is_import_eligible(pt)
    rec["needs_drilldown"] = is_entry_page(pt) and pt != "aggregator"
    if is_entry_page(pt):
        rec["_should_select"] = False   # 入口页永不默认勾选
    return rec
