"""诊断脚本：针对单个 URL 做完整抓取诊断，不写入数据库。
用法：python scripts/debug_url_fetch.py "<URL>"
"""
import sys
import os
from pathlib import Path

# 加入项目根目录
ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

def main():
    if len(sys.argv) < 2:
        print("用法: python scripts/debug_url_fetch.py \"<URL>\"")
        sys.exit(1)

    url = sys.argv[1].strip()
    print(f"\n{'='*60}")
    print(f"诊断 URL: {url}")
    print(f"{'='*60}\n")

    # 1. URL 校验
    from services.url_normalizer import is_valid_url, normalize_url
    print(f"[1] URL 校验: {'有效' if is_valid_url(url) else '无效'}")
    print(f"    normalized_url: {normalize_url(url)}")

    # 2. 来源识别
    from services.source_detector import detect_both
    detected = detect_both(url)
    print(f"\n[2] 来源识别:")
    print(f"    competitor:      {detected['competitor']}")
    print(f"    source_platform: {detected['source_platform']}")

    # 3. 代理环境变量检查
    proxy_vars = {k: v for k, v in os.environ.items()
                  if k.lower() in ("http_proxy", "https_proxy", "all_proxy", "no_proxy")}
    print(f"\n[3] 代理环境变量: {proxy_vars if proxy_vars else '（无）'}")

    # 4. 真实 HTTP 请求
    try:
        import requests
    except ImportError:
        print("\n[ERROR] requests 未安装，请运行: pip install requests")
        sys.exit(1)

    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0.0.0 Safari/537.36"
        ),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
    }

    print(f"\n[4] 发送 GET 请求...")
    print(f"    User-Agent: {headers['User-Agent'][:60]}...")

    resp = None
    exc_type = None
    exc_msg = None

    try:
        resp = requests.get(url, headers=headers, timeout=(10, 20),
                            allow_redirects=True, verify=True)
    except requests.exceptions.SSLError as e:
        exc_type = "SSLError"
        exc_msg = str(e)[:200]
    except requests.exceptions.ConnectTimeout as e:
        exc_type = "ConnectTimeout"
        exc_msg = str(e)[:200]
    except requests.exceptions.ReadTimeout as e:
        exc_type = "ReadTimeout"
        exc_msg = str(e)[:200]
    except requests.exceptions.ConnectionError as e:
        exc_type = "ConnectionError"
        exc_msg = str(e)[:200]
    except requests.exceptions.TooManyRedirects as e:
        exc_type = "TooManyRedirects"
        exc_msg = str(e)[:200]
    except Exception as e:
        exc_type = type(e).__name__
        exc_msg = str(e)[:200]

    if exc_type:
        print(f"\n    exception_type:    {exc_type}")
        print(f"    exception_message: {exc_msg}")
        print(f"\n[结论] fetch_status: failed  |  fetch_error: {exc_type}: {exc_msg[:80]}")
        return

    # 5. 响应信息
    print(f"\n[5] 响应信息:")
    print(f"    status_code:  {resp.status_code}")
    print(f"    content-type: {resp.headers.get('Content-Type', '(未知)')}")
    print(f"    final_url:    {resp.url}")
    if resp.history:
        print(f"    redirects:    {len(resp.history)} 次")
        for r in resp.history:
            print(f"                  {r.status_code} -> {r.url[:80]}")
    else:
        print(f"    redirects:    无")

    print(f"\n[6] 响应正文前 300 字符:")
    print(f"    {repr(resp.text[:300])}")

    # 6. HTML 解析
    try:
        from bs4 import BeautifulSoup
    except ImportError:
        print("\n[ERROR] beautifulsoup4 未安装")
        return

    if resp.status_code in (401, 403, 429):
        print(f"\n[结论] fetch_status: restricted  |  fetch_error: HTTP {resp.status_code}")
        return

    if resp.status_code != 200:
        print(f"\n[结论] fetch_status: failed  |  fetch_error: HTTP {resp.status_code}")
        return

    print(f"\n[7] HTML 解析:")
    try:
        soup = BeautifulSoup(resp.text, "html.parser")
    except Exception as e:
        print(f"    HTML parse error: {e}")
        print(f"\n[结论] fetch_status: failed  |  fetch_error: HTML parse error: {e}")
        return

    og_title = ""
    og_meta = soup.find("meta", attrs={"property": "og:title"})
    if og_meta and og_meta.get("content"):
        og_title = og_meta["content"].strip()

    html_title = ""
    if soup.title and soup.title.string:
        html_title = soup.title.string.strip()

    title = og_title or html_title
    print(f"    og:title:   {repr(og_title[:80])}")
    print(f"    html title: {repr(html_title[:80])}")
    print(f"    final title: {repr(title[:80])}")

    # 7. 发布时间
    pub_date = ""
    art_time = soup.find("meta", attrs={"property": "article:published_time"})
    if art_time and art_time.get("content"):
        pub_date = art_time["content"].strip()

    if not pub_date:
        import json, re
        for tag in soup.find_all("script", type="application/ld+json"):
            try:
                data = json.loads(tag.string or "")
                if isinstance(data, dict) and data.get("datePublished"):
                    pub_date = data["datePublished"]
                    break
                if isinstance(data, list):
                    for item in data:
                        if isinstance(item, dict) and item.get("datePublished"):
                            pub_date = item["datePublished"]
                            break
            except Exception:
                continue

    if not pub_date:
        time_tag = soup.find("time", attrs={"datetime": True})
        if time_tag:
            pub_date = time_tag["datetime"].strip()

    print(f"    published_date: {repr(pub_date)}")

    # 8. 最终状态
    if title:
        fetch_status = "success"
    else:
        fetch_status = "partial"
        print(f"\n    注意：未提取到标题，这是 partial（不是 failed）")

    print(f"\n[结论] fetch_status: {fetch_status}")
    if not title:
        print(f"        fetch_error: No title found")


if __name__ == "__main__":
    main()
