"""来源平台和竞品自动识别（校准版）
新增：
- X 账号映射（从 official_accounts.yaml 读取）
- LinkedIn slug 竞品识别
- GitHub 竞品关键词来自 URL path（exa-labs 等）
"""
import re
from pathlib import Path
from urllib.parse import urlparse

try:
    import yaml as _yaml
    _HAS_YAML = True
except ImportError:
    _HAS_YAML = False

_ACCOUNTS_CONFIG = Path(__file__).parent.parent / "config" / "official_accounts.yaml"

# ── 账号映射缓存 ──────────────────────────────────────────────
_account_map: dict | None = None  # {username_lower: competitor}
_linkedin_map: dict | None = None  # {slug_lower: competitor}


def _load_account_maps() -> tuple[dict, dict]:
    global _account_map, _linkedin_map
    if _account_map is not None:
        return _account_map, _linkedin_map

    x_map: dict[str, str] = {}
    li_map: dict[str, str] = {}

    if _HAS_YAML and _ACCOUNTS_CONFIG.exists():
        try:
            with open(_ACCOUNTS_CONFIG, encoding="utf-8") as f:
                data = _yaml.safe_load(f) or {}
            for competitor, accounts in data.items():
                if isinstance(accounts, dict):
                    for handle in accounts.get("x", []) or []:
                        x_map[handle.lower()] = competitor
                    for slug in accounts.get("linkedin_slugs", []) or []:
                        li_map[slug.lower()] = competitor
        except Exception:
            pass

    _account_map = x_map
    _linkedin_map = li_map
    return x_map, li_map


def _extract_x_username(url: str) -> str:
    """从 x.com/{username}/... 提取 username。"""
    try:
        path = urlparse(url).path.strip("/")
        parts = [p for p in path.split("/") if p]
        if parts:
            return parts[0]
    except Exception:
        pass
    return ""


def _extract_linkedin_slug(url: str) -> str:
    """从 linkedin.com/company/{slug} 或 /in/{slug} 等提取 slug。"""
    try:
        path = urlparse(url).path.strip("/").lower()
        # /company/slug, /posts/slug, /in/slug
        match = re.search(r"(?:company|in|posts|school|org)/([^/?#]+)", path)
        if match:
            return match.group(1)
    except Exception:
        pass
    return ""


# ── 竞品识别规则 ──────────────────────────────────────────────
_COMPETITOR_RULES: list[tuple[list[str], str]] = [
    (["tavily.com", "tavily-ai", "tavily_ai"], "Tavily"),
    (["exa.ai", "exa-labs", "exaailabs", "exa_ai"], "Exa"),
    (["brave.com", "brave-browser"], "Brave"),
    (["querit.com"], "Querit"),
]

# 第三方平台（luma 等）URL path 竞品提示
_PATH_COMPETITOR_HINTS: list[tuple[str, str]] = [
    ("tavily", "Tavily"),
    ("exa-", "Exa"),
    ("exa_", "Exa"),
    ("brave", "Brave"),
    ("querit", "Querit"),
]


def _netloc(url: str) -> str:
    try:
        netloc = urlparse(url).netloc.lower()
        if netloc.startswith("www."):
            netloc = netloc[4:]
        return netloc
    except Exception:
        return ""


def _path(url: str) -> str:
    try:
        return urlparse(url).path.lower()
    except Exception:
        return ""


def detect_competitor(url: str) -> str:
    """根据 URL 域名、账号映射和 path hint 返回竞品名称。"""
    netloc = _netloc(url)
    full = url.lower()
    x_map, li_map = _load_account_maps()

    # X 账号映射（最优先）
    if netloc in ("x.com", "twitter.com"):
        username = _extract_x_username(url)
        if username:
            competitor = x_map.get(username.lower())
            if competitor:
                return competitor
        # 页面全文关键词兜底
        for hint, comp in _PATH_COMPETITOR_HINTS:
            if hint in full:
                return comp
        return "Other"

    # LinkedIn slug 映射
    if "linkedin.com" in netloc:
        slug = _extract_linkedin_slug(url)
        if slug:
            competitor = li_map.get(slug.lower())
            if competitor:
                return competitor
        # slug 全文关键词兜底
        for hint, comp in _PATH_COMPETITOR_HINTS:
            if hint in full:
                return comp
        return "Other"

    # 域名规则
    for keywords, competitor in _COMPETITOR_RULES:
        for kw in keywords:
            if kw in netloc or kw in full:
                return competitor

    # 第三方平台 path hint（luma 等）
    url_path = _path(url)
    for hint, competitor in _PATH_COMPETITOR_HINTS:
        if hint in url_path:
            return competitor

    return "Other"


def detect_platform(url: str) -> str:
    """根据 URL 返回来源平台。"""
    netloc = _netloc(url)
    url_path = _path(url)

    if netloc in ("github.com", "raw.githubusercontent.com"):
        return "GitHub"
    if netloc in ("x.com", "twitter.com"):
        return "X"
    if "linkedin.com" in netloc:
        return "LinkedIn"
    if netloc in ("discord.com", "discord.gg"):
        return "Discord"
    if netloc in ("lu.ma", "luma.com"):
        return "Event"
    if "reddit.com" in netloc:
        return "Reddit"
    if netloc in ("youtube.com", "www.youtube.com", "youtu.be", "m.youtube.com"):
        return "YouTube"

    if netloc.startswith("docs.") or netloc.startswith("api."):
        return "官网"

    _KNOWN_COMPETITOR_DOMAINS = {
        kw for keywords, _ in _COMPETITOR_RULES for kw in keywords
    }
    is_known_domain = any(kw in netloc for kw in _KNOWN_COMPETITOR_DOMAINS)

    if is_known_domain:
        if netloc.startswith("blog."):
            return "Blog"
        if "/blog/" in url_path or url_path.startswith("/blog"):
            return "Blog"
        if "/news/" in url_path or url_path.startswith("/news"):
            return "Blog"
        if "/changelog" in url_path:
            return "Blog"

    if "medium.com" in netloc or "substack.com" in netloc:
        return "Blog"
    # 第三方技术博客（非竞品官方域名，含博文路径特征）
    if not is_known_domain and ("/blog/" in url_path or url_path.startswith("/blog") or "/post/" in url_path):
        return "第三方Blog"

    if is_known_domain:
        return "官网"

    return "Other"


def detect_both(url: str, title: str = "", description: str = "") -> dict:
    """返回 {competitor, source_platform}。
    title/description 可辅助判断（如 X 帖子标题含竞品名）。
    """
    competitor = detect_competitor(url)

    # X/LinkedIn 帖子：若 URL 未能判断，尝试从 title/description 辅助
    if competitor == "Other" and (title or description):
        combined = f"{title} {description}".lower()
        for hint, comp in _PATH_COMPETITOR_HINTS:
            if hint.rstrip("-_") in combined:
                competitor = comp
                break

    return {
        "competitor": competitor,
        "source_platform": detect_platform(url),
    }


def invalidate_account_cache() -> None:
    """清除账号映射缓存（用于测试）。"""
    global _account_map, _linkedin_map
    _account_map = None
    _linkedin_map = None
