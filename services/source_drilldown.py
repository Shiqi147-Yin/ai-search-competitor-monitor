"""入口页二次下钻服务
对 blog_index / docs_index / github_repository / github_organization / event_index
执行下钻，提取时间窗口内的具体内容页。
最大下钻深度 1，每入口最多 20 条，不递归。
"""
import json
import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from typing import Optional
from urllib.parse import urlparse, urljoin

try:
    import requests as _req
    _HAS_REQUESTS = True
except ImportError:
    _HAS_REQUESTS = False

try:
    from bs4 import BeautifulSoup as _BS
    _HAS_BS4 = True
except ImportError:
    _HAS_BS4 = False

from services.page_type_classifier import classify_page_type

_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)
_TIMEOUT = (10, 20)
_MAX_ITEMS_PER_ENTRY = 20

# ── 月份映射 ─────────────────────────────────────────────────────
_MONTH_SHORT = {
    "jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
    "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12,
}
_MONTH_FULL = {
    "january": 1, "february": 2, "march": 3, "april": 4, "may": 5, "june": 6,
    "july": 7, "august": 8, "september": 9, "october": 10, "november": 11, "december": 12,
}

# 类别关键词（用于从标题中剔除）
_BLOG_CATEGORY_WORDS = {
    "product", "news", "engineering", "research", "case study",
    "customer", "featured", "tutorial", "announcement", "release",
}

# 日期模式匹配
_DATE_PATTERN = re.compile(
    r"\b(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?\s+(\d{1,2})(?:,\s*(\d{4}))?\b"
    r"|(\d{4})-(\d{2})-(\d{2})",
    re.IGNORECASE,
)


@dataclass
class DiscoveredItem:
    source_url: str = ""
    title: str = ""
    published_date: str = ""    # 首次发布时间（Blog 文章用）
    updated_at: str = ""        # 最后更新时间（Docs sitemap lastmod 用）
    page_type: str = "unknown"
    parent_entry_url: str = ""
    discovery_method: str = ""
    within_window: bool = False
    import_eligible: bool = True
    is_entry_page: bool = False


@dataclass
class DrilldownResult:
    source_url: str = ""
    page_type: str = ""
    drilldown_status: str = "pending"  # success|partial|failed|not_needed
    discovered_items: list = field(default_factory=list)  # list[DiscoveredItem]
    error: str = ""


def _get(url: str, accept: str = "text/html") -> tuple[int, str]:
    if not _HAS_REQUESTS:
        return -1, "requests not installed"
    try:
        r = _req.get(url, headers={"User-Agent": _UA, "Accept": accept},
                     timeout=_TIMEOUT, allow_redirects=True)
        return r.status_code, r.text
    except Exception as e:
        return -1, str(e)[:120]


def _within_window(date_str: str, window_start: str, window_end: str) -> bool:
    """判断 date_str 是否在时间窗口内。"""
    if not date_str:
        return False
    try:
        from datetime import datetime, timezone

        def _parse(s: str):
            s = s.strip()
            for fmt in (
                "%Y-%m-%dT%H:%M:%SZ",
                "%Y-%m-%dT%H:%M:%S.%fZ",
                "%Y-%m-%dT%H:%M:%S%z",
                "%Y-%m-%d %H:%M:%S",
                "%Y-%m-%d",
            ):
                try:
                    d = datetime.strptime(s, fmt)
                    if d.tzinfo is None:
                        d = d.replace(tzinfo=timezone.utc)
                    return d
                except Exception:
                    continue
            try:
                d = datetime.fromisoformat(s.replace("Z", "+00:00"))
                if d.tzinfo is None:
                    d = d.replace(tzinfo=timezone.utc)
                return d
            except Exception:
                return None

        dt = _parse(date_str)
        ws = _parse(window_start)
        we = _parse(window_end)
        if dt is None or ws is None or we is None:
            return False
        return ws <= dt <= we
    except Exception:
        return False


def _parse_blog_card_date(text: str, window_end: str = "") -> tuple[str, str]:
    """从 Blog 卡片文本中提取日期，返回 (published_date_iso, cleaned_title)。
    支持：Jul 14 / Jul 14, 2026 / July 14 / July 14, 2026 / 2026-07-14
    无年份时用 window_end 年份（或当前年）补全，并处理跨年逻辑。
    """
    m = _DATE_PATTERN.search(text)
    if not m:
        return "", text

    try:
        if m.group(4):
            # YYYY-MM-DD 格式
            year, month, day = int(m.group(4)), int(m.group(5)), int(m.group(6))
        else:
            month_str = m.group(1).lower()[:3]
            day = int(m.group(2))
            month = _MONTH_SHORT.get(month_str) or _MONTH_FULL.get(m.group(1).lower(), 0)
            if not month:
                return "", text
            if m.group(3):
                year = int(m.group(3))
            else:
                # 无年份：使用 window_end 年份，处理跨年
                ref_year = datetime.now(timezone.utc).year
                if window_end:
                    try:
                        we = datetime.fromisoformat(window_end.replace("Z", "+00:00"))
                        ref_year = we.year
                    except Exception:
                        pass
                # 如果 month 比 window_end 月份大很多，可能是上一年
                year = ref_year

        date_iso = f"{year}-{month:02d}-{day:02d}T00:00:00Z"
        # 从 text 中去掉日期及其周围的间隔符和类别词
        cleaned = text[:m.start()] + text[m.end():]
        # 去除类别词（支持粘连情况，如 "Dataproduct" 中的 product）
        for cw in _BLOG_CATEGORY_WORDS:
            # 先尝试整词匹配（带边界）
            cleaned = re.sub(r'\b' + re.escape(cw) + r'\b', '', cleaned, flags=re.IGNORECASE)
            # 再尝试粘连匹配（如 Dataproduct → Data）
            cleaned = re.sub(re.escape(cw), '', cleaned, flags=re.IGNORECASE)
        # 去除多余分隔符（·、•、|、-、,）和多余空白
        cleaned = re.sub(r'[·•|]', ' ', cleaned)
        cleaned = re.sub(r'\s{2,}', ' ', cleaned).strip().strip(',').strip()
        return date_iso, cleaned
    except Exception:
        return "", text


# ── Blog 下钻 ──────────────────────────────────────────────────

def drilldown_blog(url: str, window_start: str, window_end: str) -> DrilldownResult:
    result = DrilldownResult(source_url=url, page_type="blog_index")
    if not _HAS_REQUESTS or not _HAS_BS4:
        result.drilldown_status = "failed"
        result.error = "requests 或 beautifulsoup4 未安装"
        return result

    code, html = _get(url)
    if code != 200:
        result.drilldown_status = "failed"
        result.error = f"HTTP {code}"
        return result

    try:
        soup = _BS(html, "html.parser")
    except Exception as e:
        result.drilldown_status = "failed"
        result.error = f"HTML 解析失败: {e}"
        return result

    domain = urlparse(url).scheme + "://" + urlparse(url).netloc
    items: list[DiscoveredItem] = []
    seen: set[str] = set()

    # 通用文章链接提取：查找 <article>、<li>、<a> 中有 blog 路径或 time 标签
    article_links = []

    # 策略 1：<article> 容器（独立遍历，不与 <li> 共享 limit）
    # 注意：不能与 <li> 合并查找后加 limit，否则 nav li 过多会把 article 挤出范围
    _strategy1_containers = list(soup.find_all("article", limit=30))
    _strategy1_containers += [
        li for li in soup.find_all("li", limit=50)
        if li.find("a", href=True) and "/blog/" in (
            li.find("a", href=True).get("href", "")
            if li.find("a", href=True).get("href", "").startswith("http")
            else urljoin(domain, li.find("a", href=True).get("href", ""))
        )
    ]
    for container in _strategy1_containers:
        a_tag = container.find("a", href=True)
        time_tag = container.find("time")
        if not a_tag:
            continue
        href = a_tag.get("href", "")
        if not href:
            continue
        full_url = href if href.startswith("http") else urljoin(domain, href)

        # 只处理 /blog/ 路径的链接（否则会误抓导航）
        if "/blog/" not in full_url:
            continue
        # 跳过分页链接
        if re.search(r"/blog/page/\d+", full_url):
            continue

        # 从 time 标签或 datetime 属性获取日期
        if time_tag:
            pub_date = time_tag.get("datetime", "") or time_tag.get_text(strip=True)
            # 尝试从 time 文本解析
            if pub_date and not pub_date.startswith("20"):
                parsed_date, _ = _parse_blog_card_date(pub_date, window_end)
                pub_date = parsed_date
        else:
            pub_date = ""

        # 提取标题并清理
        title_el = container.find(["h1", "h2", "h3", "h4"])
        if title_el:
            raw_title = title_el.get_text(strip=True)
        else:
            raw_title = a_tag.get_text(separator=" ", strip=True)

        # 如果标题含日期，尝试清理
        if not pub_date:
            pub_date, raw_title = _parse_blog_card_date(raw_title, window_end)

        # 如果标题和 time 标签均无日期，扫描容器内 <p> 标签（Brave Blog 等将日期放在 <p> 内）
        if not pub_date:
            for p_tag in container.find_all("p"):
                p_text = p_tag.get_text(strip=True)
                candidate, _ = _parse_blog_card_date(p_text, window_end)
                if candidate:
                    pub_date = candidate
                    break

        article_links.append((full_url, raw_title, pub_date))

    # 策略 2：带 /blog/ 路径的 <a>（Tavily Blog 是 SPA，这是主要策略）
    if not article_links:
        for a in soup.find_all("a", href=True, limit=200):
            href = a.get("href", "")
            full_url = href if href.startswith("http") else urljoin(domain, href)
            if "/blog/" in full_url and full_url != url:
                # 跳过分页链接（/blog/page/N/）
                if re.search(r"/blog/page/\d+", full_url):
                    continue
                raw_text = a.get_text(separator=" ", strip=True)
                # 从文本中提取日期并清理标题
                pub_date, clean_title = _parse_blog_card_date(raw_text, window_end)
                if not clean_title:
                    clean_title = a.get_text(strip=True)
                article_links.append((full_url, clean_title, pub_date))

    for full_url, title, pub_date in article_links:
        if full_url in seen or full_url == url:
            continue
        pt = classify_page_type(full_url, title)
        if pt not in ("detail_article", "blog_index"):
            continue
        if pt == "blog_index":
            continue

        seen.add(full_url)
        in_win = _within_window(pub_date, window_start, window_end) if pub_date else None
        items.append(DiscoveredItem(
            source_url=full_url,
            title=title[:120],
            published_date=pub_date,
            page_type="detail_article",
            parent_entry_url=url,
            discovery_method="blog_index_drilldown",
            within_window=bool(in_win) if pub_date else False,
            import_eligible=True,
        ))
        if len(items) >= _MAX_ITEMS_PER_ENTRY:
            break

    result.discovered_items = items
    result.drilldown_status = "success" if items else "partial"
    if not items:
        result.error = "未发现具体文章链接"
    return result


# ── Docs 下钻 ──────────────────────────────────────────────────

def drilldown_docs(url: str, window_start: str, window_end: str) -> DrilldownResult:
    result = DrilldownResult(source_url=url, page_type="docs_index")

    # 先尝试 sitemap.xml
    parsed = urlparse(url)
    base = f"{parsed.scheme}://{parsed.netloc}"
    sitemap_url = base + "/sitemap.xml"
    code, xml_text = _get(sitemap_url, accept="application/xml,text/xml")

    items: list[DiscoveredItem] = []
    seen: set[str] = set()

    # 检测是否为 sitemapindex，若是则递归读取子 sitemap（最多展开一层）
    if code == 200:
        try:
            root_check = ET.fromstring(xml_text)
            ns_si = {"si": "http://www.sitemaps.org/schemas/sitemap/0.9"}
            child_sitemaps = root_check.findall(".//si:sitemap/si:loc", ns_si)
            if child_sitemaps:
                # 是 sitemapindex：找最相关的子 sitemap（优先含 entry path 的）
                entry_path = parsed.path.strip("/")  # e.g. "search/api"
                chosen = None
                for child_loc in child_sitemaps:
                    if child_loc.text and entry_path and any(
                        seg in (child_loc.text or "") for seg in entry_path.split("/") if len(seg) > 2
                    ):
                        chosen = child_loc.text
                        break
                # 若无匹配则取第一个子 sitemap
                if not chosen and child_sitemaps:
                    chosen = child_sitemaps[0].text
                if chosen:
                    c2, xml_text2 = _get(chosen, accept="application/xml,text/xml")
                    if c2 == 200:
                        xml_text = xml_text2
                        sitemap_url = chosen
        except Exception:
            pass  # 保持 xml_text 原值继续

    items: list[DiscoveredItem] = []
    seen: set[str] = set()

    if code == 200:
        try:
            root = ET.fromstring(xml_text)
            ns = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}

            # 关键词优先：nemo/nvidia 优先级最高
            priority_patterns = [
                "nemo", "nvidia", "integration", "changelog", "mcp", "sdk",
                "api", "example", "quickstart", "release", "agent",
            ]

            # 读取全部 URL（不截断）
            all_urls: list[tuple[str, str]] = []
            for url_el in root.findall(".//sm:url", ns):
                loc = url_el.findtext("sm:loc", "", ns) or ""
                lastmod = url_el.findtext("sm:lastmod", "", ns) or ""
                if not loc:
                    continue
                if urlparse(loc).path.strip("/") == "":
                    continue   # 跳过首页
                all_urls.append((loc, lastmod))

            # 步骤 1：时间窗口过滤（先过滤，再 limit）
            window_items: list[tuple[str, str, bool]] = []   # (loc, lastmod, is_priority)
            non_window_priority: list[tuple[str, str]] = []

            for loc, lastmod in all_urls:
                path_lower = urlparse(loc).path.lower()
                in_win = _within_window(lastmod, window_start, window_end) if lastmod else False
                is_priority = any(p in path_lower for p in priority_patterns)

                if in_win:
                    window_items.append((loc, lastmod, is_priority))
                elif is_priority:
                    non_window_priority.append((loc, lastmod))

            # 步骤 2：排序：窗口内高优先 > 窗口内其他 > 窗口外高优先
            window_items.sort(key=lambda x: (not x[2], x[1] or ""), reverse=False)
            window_items.sort(key=lambda x: x[2], reverse=True)   # is_priority 优先

            # 步骤 3：合并并限制数量
            candidates = [(loc, lastmod) for loc, lastmod, _ in window_items]
            # 补充窗口外高优先（用于诊断，不占窗口内名额）
            for loc, lastmod in non_window_priority:
                candidates.append((loc, lastmod))

            for loc, lastmod in candidates[:_MAX_ITEMS_PER_ENTRY]:
                if loc in seen:
                    continue
                seen.add(loc)
                in_win = _within_window(lastmod, window_start, window_end) if lastmod else False
                items.append(DiscoveredItem(
                    source_url=loc,
                    title=loc.split("/")[-1].replace("-", " ").title(),
                    published_date="",           # sitemap lastmod 是更新时间，不是发布时间
                    updated_at=lastmod,          # 放入 updated_at
                    page_type="docs_detail",
                    parent_entry_url=url,
                    discovery_method="sitemap_lastmod",
                    within_window=in_win,
                    import_eligible=True,
                ))

        except Exception as e:
            result.error = f"sitemap 解析失败: {e}"

    result.discovered_items = items
    result.drilldown_status = "success" if items else "partial"
    if not items and not result.error:
        result.error = "sitemap 无时间窗口内文档更新"
    return result


# ── GitHub 下钻 ─────────────────────────────────────────────────

def drilldown_github(url: str, window_start: str, window_end: str) -> DrilldownResult:
    """复用现有 github_fetcher，提取 commits 和 releases。"""
    from services.github_url_parser import parse_github_url
    from services.github_fetcher import fetch_github

    result = DrilldownResult(source_url=url, page_type="github_repository")
    parsed = parse_github_url(url)

    if not parsed.owner or not parsed.repo:
        result.drilldown_status = "failed"
        result.error = "无法解析 owner/repo"
        return result

    items: list[DiscoveredItem] = []

    # 拼接 commits 列表 URL（带时间范围）
    commits_url = (
        f"https://github.com/{parsed.owner}/{parsed.repo}/commits/main"
        f"?since={window_start}&until={window_end}"
    )
    gh_result = fetch_github(commits_url)
    for commit in gh_result.commits[:_MAX_ITEMS_PER_ENTRY]:
        in_win = _within_window(commit.date, window_start, window_end) if commit.date else True
        items.append(DiscoveredItem(
            source_url=commit.url or f"https://github.com/{parsed.owner}/{parsed.repo}/commit/{commit.sha}",
            title=commit.title[:120],
            published_date=commit.date,
            page_type="github_commit",
            parent_entry_url=url,
            discovery_method="github_commits_api",
            within_window=in_win,
            import_eligible=True,
        ))

    # releases
    releases_url = f"https://github.com/{parsed.owner}/{parsed.repo}/releases"
    rel_result = fetch_github(releases_url)
    if rel_result.title and rel_result.published_date:
        in_win = _within_window(rel_result.published_date, window_start, window_end)
        items.append(DiscoveredItem(
            source_url=releases_url,
            title=rel_result.title[:120],
            published_date=rel_result.published_date,
            page_type="github_release",
            parent_entry_url=url,
            discovery_method="github_releases_api",
            within_window=in_win,
            import_eligible=True,
        ))

    result.discovered_items = items
    result.drilldown_status = "success" if items else "partial"
    if not items:
        result.error = "未发现时间窗口内的 commits 或 releases"
    return result


# ── Event 下钻 ─────────────────────────────────────────────────

def drilldown_event(url: str, window_start: str, window_end: str) -> DrilldownResult:
    result = DrilldownResult(source_url=url, page_type="event_index")
    if not _HAS_REQUESTS or not _HAS_BS4:
        result.drilldown_status = "failed"
        result.error = "requests 或 beautifulsoup4 未安装"
        return result

    code, html = _get(url)
    if code != 200:
        result.drilldown_status = "failed"
        result.error = f"HTTP {code}"
        return result

    try:
        soup = _BS(html, "html.parser")
    except Exception as e:
        result.drilldown_status = "failed"
        result.error = f"HTML 解析失败: {e}"
        return result

    domain = urlparse(url).scheme + "://" + urlparse(url).netloc
    items: list[DiscoveredItem] = []
    seen: set[str] = set()

    for a in soup.find_all("a", href=True, limit=100):
        href = a.get("href", "")
        full_url = href if href.startswith("http") else urljoin(domain, href)
        if full_url in seen or full_url == url:
            continue
        pt = classify_page_type(full_url)
        if pt == "event_detail":
            seen.add(full_url)
            title = a.get_text(strip=True)
            items.append(DiscoveredItem(
                source_url=full_url,
                title=title[:120],
                page_type="event_detail",
                parent_entry_url=url,
                discovery_method="event_index_drilldown",
                import_eligible=True,
            ))
        if len(items) >= _MAX_ITEMS_PER_ENTRY:
            break

    result.discovered_items = items
    result.drilldown_status = "success" if items else "partial"
    if not items:
        result.error = "未发现具体活动链接"
    return result


# ── 统一入口 ─────────────────────────────────────────────────────

def drilldown_result(
    rec: dict,
    window_start: str,
    window_end: str,
) -> "DrilldownResult":
    """对单条结果执行下钻（仅入口页触发）。单个失败捕获异常，返回 failed 状态。"""
    url = rec.get("source_url") or rec.get("url") or ""
    page_type = rec.get("page_type") or classify_page_type(url)

    if page_type in ("detail_article", "docs_detail", "github_commit",
                     "github_release", "social_post", "event_detail"):
        return DrilldownResult(source_url=url, page_type=page_type,
                               drilldown_status="not_needed")

    if page_type == "aggregator":
        return DrilldownResult(source_url=url, page_type=page_type,
                               drilldown_status="not_needed",
                               error="聚合页，跳过下钻")

    try:
        if page_type in ("blog_index",):
            return drilldown_blog(url, window_start, window_end)
        if page_type in ("docs_index",):
            return drilldown_docs(url, window_start, window_end)
        if page_type in ("github_repository", "github_organization",
                         "github_commits_list"):
            return drilldown_github(url, window_start, window_end)
        if page_type in ("event_index",):
            return drilldown_event(url, window_start, window_end)
    except Exception as e:
        return DrilldownResult(source_url=url, page_type=page_type,
                               drilldown_status="failed",
                               error=f"{type(e).__name__}: {str(e)[:80]}")

    return DrilldownResult(source_url=url, page_type=page_type,
                           drilldown_status="not_needed")
