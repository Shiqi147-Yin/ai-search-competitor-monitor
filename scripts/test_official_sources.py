"""scripts/test_official_sources.py
逐个测试官方来源入口的可访问性和基本解析能力。
用法：
    python scripts/test_official_sources.py --competitor Exa
    python scripts/test_official_sources.py --competitor Tavily
    python scripts/test_official_sources.py  # 测试全部
"""
import sys
import os
import argparse
import xml.etree.ElementTree as ET
from urllib.parse import urlparse

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

try:
    import requests as _req
    _HAS_REQUESTS = True
except ImportError:
    _HAS_REQUESTS = False

try:
    import yaml as _yaml
    _HAS_YAML = True
except ImportError:
    _HAS_YAML = False

from services.page_type_classifier import classify_page_type

_CONFIG_PATH = os.path.join(_ROOT, "config", "official_monitoring_sources.yaml")
_UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
_TIMEOUT = (8, 15)


def _get(url: str) -> tuple[int, str]:
    if not _HAS_REQUESTS:
        return -1, "requests not installed"
    try:
        r = _req.get(url, headers={"User-Agent": _UA}, timeout=_TIMEOUT, allow_redirects=True)
        return r.status_code, r.text
    except Exception as e:
        return -1, str(e)[:100]


def _count_sitemap_urls(xml_text: str) -> int:
    try:
        root = ET.fromstring(xml_text)
        ns = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}
        return len(root.findall(".//sm:url", ns))
    except Exception:
        return 0


def _has_date_info(text: str) -> bool:
    import re
    return bool(re.search(r"(lastmod|published|date|datetime)", text, re.I))


def test_url(source_type: str, url: str) -> dict:
    result = {
        "source_type": source_type,
        "url": url,
        "http_status": None,
        "page_type": None,
        "parseable": False,
        "sitemap_url_count": None,
        "has_date_info": False,
        "error": "",
    }
    code, text = _get(url)
    result["http_status"] = code
    if code == 200:
        result["parseable"] = True
        result["has_date_info"] = _has_date_info(text[:5000])
        result["page_type"] = classify_page_type(url, "")
        if "sitemap" in source_type.lower() or url.endswith(".xml"):
            result["sitemap_url_count"] = _count_sitemap_urls(text)
    elif code == -1:
        result["error"] = text
    return result


def print_result(r: dict, idx: int):
    status_str = str(r["http_status"]) if r["http_status"] else "ERR"
    ok = "OK  " if r["http_status"] == 200 else "FAIL"
    print(f"  [{ok}] [{idx:02d}] {r['source_type']:20s}  HTTP {status_str:3s}  {r['url'][:70]}")
    if r["page_type"]:
        print(f"         page_type={r['page_type']}  has_date={r['has_date_info']}  parseable={r['parseable']}", end="")
        if r["sitemap_url_count"] is not None:
            print(f"  sitemap_urls={r['sitemap_url_count']}", end="")
        print()
    if r["error"]:
        print(f"         error: {r['error']}")


def main():
    parser = argparse.ArgumentParser(description="测试官方来源入口可访问性")
    parser.add_argument("--competitor", default=None, help="竞品名称（留空=全部）")
    args = parser.parse_args()

    if not _HAS_YAML:
        print("ERROR: pyyaml not installed")
        sys.exit(1)
    if not _HAS_REQUESTS:
        print("ERROR: requests not installed")
        sys.exit(1)

    with open(_CONFIG_PATH, encoding="utf-8") as f:
        config = _yaml.safe_load(f) or {}

    competitors = [args.competitor] if args.competitor else list(config.keys())

    for competitor in competitors:
        if competitor not in config:
            print(f"\n[{competitor}] 未在配置中找到，跳过。")
            continue

        print(f"\n{'='*60}")
        print(f"  {competitor} 官方来源入口测试")
        print(f"{'='*60}")

        comp_config = config[competitor]
        website = comp_config.get("website", {})
        github_conf = comp_config.get("github", {})

        results = []
        idx = 0

        # 网站入口
        for source_type, urls in website.items():
            if not isinstance(urls, list):
                continue
            for url in urls:
                idx += 1
                r = test_url(source_type, url)
                results.append(r)
                print_result(r, idx)

        # GitHub 仓库入口
        owner = github_conf.get("owner", "")
        for repo_cfg in github_conf.get("repositories", []):
            repo_name = repo_cfg.get("name", "") if isinstance(repo_cfg, dict) else repo_cfg
            if not repo_name:
                continue
            url = f"https://github.com/{owner}/{repo_name}"
            idx += 1
            r = test_url("github_repo", url)
            results.append(r)
            print_result(r, idx)
            # Atom feed
            atom_url = f"https://github.com/{owner}/{repo_name}/commits/main.atom"
            idx += 1
            r_atom = test_url("github_atom_feed", atom_url)
            results.append(r_atom)
            print_result(r_atom, idx)

        # 汇总
        ok_count = sum(1 for r in results if r["http_status"] == 200)
        fail_count = len(results) - ok_count
        print(f"\n  汇总: 成功 {ok_count}/{len(results)}，失败 {fail_count}")

    print()


if __name__ == "__main__":
    main()
