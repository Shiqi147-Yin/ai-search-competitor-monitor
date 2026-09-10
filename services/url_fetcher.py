"""网页基础信息抓取服务（修订版）
修复点：
1. User-Agent 改为标准桌面浏览器标识
2. 超时调整为 connect=10s / read=20s
3. 状态判断修正：HTTP 200 + 有标题 = success；HTTP 200 + 无标题 = partial（不是 failed）
4. 各异常类型精确记录到 fetch_error
5. 403/429 一次性降级重试（换 UA + Referer）
"""
import json
import re
from dataclasses import dataclass
from urllib.parse import urljoin, urlparse

try:
    import requests
    _HAS_REQUESTS = True
except ImportError:
    _HAS_REQUESTS = False

try:
    from bs4 import BeautifulSoup
    _HAS_BS4 = True
except ImportError:
    _HAS_BS4 = False

_UA_DEFAULT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36"
)
_UA_FALLBACK = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/605.1.15 (KHTML, like Gecko) "
    "Version/17.4 Safari/605.1.15"
)
_CONNECT_TIMEOUT = 10
_READ_TIMEOUT = 20
_MAX_CONTENT_LEN = 2000


@dataclass
class FetchResult:
    url: str
    final_url: str = ""
    status: str = "pending"          # pending/success/partial/failed/restricted/unsupported
    title: str = ""
    description: str = ""
    published_date: str = ""
    content_snippet: str = ""
    error: str = ""
    content_source: str = ""
    http_status_code: int = 0


def _build_headers(ua: str, referer: str = "") -> dict:
    h = {
        "User-Agent": ua,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "Accept-Encoding": "gzip, deflate, br",
    }
    if referer:
        h["Referer"] = referer
    return h


def _origin(url: str) -> str:
    """返回 scheme://netloc 作为 Referer。"""
    p = urlparse(url)
    return f"{p.scheme}://{p.netloc}"


# HTTP 状态码 → restricted（访问受限，不视为系统失败）
_RESTRICTED_STATUS_CODES = {401, 403, 429, 451}


def fetch_url(url: str) -> FetchResult:
    """抓取 URL，所有异常均捕获，不向上抛出。"""
    result = FetchResult(url=url, final_url=url)

    if not _HAS_REQUESTS:
        result.status = "failed"
        result.error = "requests 库未安装，请执行 pip install requests"
        return result

    if not _HAS_BS4:
        result.status = "failed"
        result.error = "beautifulsoup4 库未安装，请执行 pip install beautifulsoup4"
        return result

    resp = _do_request(url, _UA_DEFAULT, "")

    # 一次降级重试：403/429 时换 UA + Referer（451 是法律限制，不重试）
    if isinstance(resp, int) and resp in (403, 429):
        resp = _do_request(url, _UA_FALLBACK, _origin(url))

    if isinstance(resp, str):
        # 字符串表示异常
        result.status = "failed"
        result.error = resp
        return result

    if isinstance(resp, int):
        result.http_status_code = resp
        if resp in _RESTRICTED_STATUS_CODES:
            result.status = "restricted"
            result.error = f"HTTP {resp}"
        else:
            result.status = "failed"
            result.error = f"HTTP {resp}"
        return result

    # resp 是 requests.Response 对象
    result.http_status_code = resp.status_code
    result.final_url = resp.url

    if resp.status_code in _RESTRICTED_STATUS_CODES:
        result.status = "restricted"
        result.error = f"HTTP {resp.status_code}"
        return result

    if resp.status_code != 200:
        result.status = "failed"
        result.error = f"HTTP {resp.status_code}"
        return result

    # 检查 content-type
    ct = resp.headers.get("Content-Type", "").lower()
    if ct and "html" not in ct and "xml" not in ct:
        result.status = "unsupported"
        result.error = f"非 HTML 内容：{ct}"
        return result

    _parse_html(resp.text, result)
    return result


def _do_request(url: str, ua: str, referer: str):
    """执行 HTTP GET，返回 Response / int(status_code) / str(error_message)。"""
    try:
        resp = requests.get(
            url,
            headers=_build_headers(ua, referer),
            timeout=(_CONNECT_TIMEOUT, _READ_TIMEOUT),
            allow_redirects=True,
        )
        return resp
    except requests.exceptions.SSLError as e:
        return f"SSLError: {str(e)[:120]}"
    except requests.exceptions.ConnectTimeout as e:
        return f"ConnectTimeout: {str(e)[:120]}"
    except requests.exceptions.ReadTimeout as e:
        return f"ReadTimeout: {str(e)[:120]}"
    except requests.exceptions.TooManyRedirects as e:
        return f"TooManyRedirects: {str(e)[:120]}"
    except requests.exceptions.ConnectionError as e:
        return f"ConnectionError: {str(e)[:120]}"
    except Exception as e:
        return f"{type(e).__name__}: {str(e)[:120]}"


def _parse_html(html: str, result: FetchResult) -> None:
    try:
        soup = BeautifulSoup(html, "html.parser")
    except Exception as e:
        result.status = "failed"
        result.error = f"HTML parse error: {e}"
        return

    # ── 标题 ──────────────────────────────────────────────────
    og_title = _meta(soup, property="og:title")
    html_title = soup.title.string.strip() if (soup.title and soup.title.string) else ""
    result.title = og_title or html_title

    # ── 描述 ──────────────────────────────────────────────────
    og_desc = _meta(soup, property="og:description")
    meta_desc = _meta(soup, name="description")
    result.description = og_desc or meta_desc

    # ── 发布时间 ───────────────────────────────────────────────
    result.published_date = (
        _meta(soup, property="article:published_time")
        or _jsonld_date(soup)
        or _time_tag(soup)
        or _meta(soup, property="og:updated_time")
        or ""
    )

    # ── 正文片段 ───────────────────────────────────────────────
    for tag in soup(["script", "style", "nav", "footer", "header", "aside"]):
        tag.decompose()
    text = soup.get_text(separator=" ", strip=True)
    text = re.sub(r"\s{2,}", " ", text)
    result.content_snippet = text[:_MAX_CONTENT_LEN]

    # ── content_source ─────────────────────────────────────────
    if og_title:
        result.content_source = "og"
    elif meta_desc:
        result.content_source = "meta"
    elif _jsonld_date(soup):
        result.content_source = "json-ld"
    else:
        result.content_source = "html"

    # ── 状态：有标题 = success；无标题 = partial（不是 failed）──
    if result.title:
        result.status = "success"
    else:
        result.status = "partial"
        result.error = "No title found"


def _meta(soup, **kwargs) -> str:
    tag = soup.find("meta", attrs=kwargs)
    if tag and tag.get("content"):
        return tag["content"].strip()
    return ""


def _jsonld_date(soup) -> str:
    for tag in soup.find_all("script", type="application/ld+json"):
        try:
            data = json.loads(tag.string or "")
            if isinstance(data, dict):
                return data.get("datePublished", "")
            if isinstance(data, list):
                for item in data:
                    if isinstance(item, dict) and item.get("datePublished"):
                        return item["datePublished"]
        except Exception:
            continue
    return ""


def _time_tag(soup) -> str:
    tag = soup.find("time", attrs={"datetime": True})
    if tag:
        return tag["datetime"].strip()
    return ""
