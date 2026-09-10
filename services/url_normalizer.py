"""URL 规范化：去追踪参数、统一 scheme、尾部斜杠去重"""
from urllib.parse import urlparse, urlunparse, urlencode, parse_qsl

# 需要去除的追踪参数
_STRIP_PARAMS = {
    "utm_source", "utm_medium", "utm_campaign", "utm_content", "utm_term",
    "ref", "fbclid", "gclid", "mc_cid", "mc_eid", "_hsenc", "_hsmi",
    "mkt_tok", "trk", "trkCampaign", "sc_campaign", "sc_channel",
}


def normalize_url(url: str) -> str:
    """规范化 URL：统一 https、去追踪参数、去 fragment、统一尾部斜杠。"""
    url = url.strip()
    if not url:
        return url

    # 补全 scheme
    if url.startswith("//"):
        url = "https:" + url
    elif not url.startswith(("http://", "https://")):
        url = "https://" + url

    try:
        parsed = urlparse(url)
    except Exception:
        return url

    # 统一 scheme 为 https
    scheme = "https"

    # 去 fragment
    fragment = ""

    # 去除追踪参数
    qs = [(k, v) for k, v in parse_qsl(parsed.query, keep_blank_values=True)
          if k.lower() not in _STRIP_PARAMS]
    query = urlencode(qs)

    # 统一 path 尾部斜杠（保留根路径 /）
    path = parsed.path
    if path != "/" and path.endswith("/"):
        path = path.rstrip("/")

    normalized = urlunparse((scheme, parsed.netloc.lower(), path, parsed.params, query, fragment))
    return normalized


def is_valid_url(url: str) -> bool:
    """基础 URL 格式校验。"""
    url = url.strip()
    if not url:
        return False
    if not url.startswith(("http://", "https://", "//")):
        # 允许省略 scheme
        url = "https://" + url
    try:
        parsed = urlparse(url)
        return bool(parsed.netloc and "." in parsed.netloc)
    except Exception:
        return False


def deduplicate_urls(urls: list[str]) -> list[str]:
    """同批次内去重，保留首次出现的 URL（基于 normalized_url）。"""
    seen: set[str] = set()
    result: list[str] = []
    for url in urls:
        norm = normalize_url(url)
        if norm not in seen:
            seen.add(norm)
            result.append(url)
    return result
