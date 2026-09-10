"""诊断脚本：检查 Querit API 真实响应结构
用法：python scripts/debug_querit_response.py --query "Latest Tavily product updates" --limit 1
不写数据库，不打印 API Key。
"""
import sys
import io
import argparse
import json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

from env_loader import load_env, get_env_bool
load_env()

import os


def _safe_truncate(obj, max_chars=300) -> str:
    """安全截断任意对象为字符串，限制长度。"""
    s = str(obj)
    if len(s) > max_chars:
        return s[:max_chars] + f"... [截断，共 {len(s)} 字符]"
    return s


def _describe_type(obj) -> str:
    t = type(obj).__name__
    if isinstance(obj, dict):
        return f"dict(keys={list(obj.keys())[:10]})"
    if isinstance(obj, list):
        return f"list(len={len(obj)}, first_type={type(obj[0]).__name__ if obj else 'empty'})"
    if isinstance(obj, str):
        return f"str(len={len(obj)})"
    return t


def main():
    parser = argparse.ArgumentParser(description="Querit API 响应结构诊断")
    parser.add_argument("--query", required=True, help="要发送的英文 Query")
    parser.add_argument("--limit", type=int, default=1, help="最多返回结果数")
    args = parser.parse_args()

    mock = get_env_bool("QUERIT_MOCK_MODE", default=True)
    if mock:
        print("当前为 Mock 模式，无法诊断真实响应。请先设置 QUERIT_MOCK_MODE=false")
        sys.exit(0)

    api_key = os.environ.get("QUERIT_API_KEY", "")
    base_url = os.environ.get("QUERIT_API_BASE_URL", "")
    search_path = os.environ.get("QUERIT_API_SEARCH_PATH", "/search")
    timeout = int(os.environ.get("QUERIT_API_TIMEOUT", "30"))

    if not api_key or not base_url:
        print("配置缺失：请设置 QUERIT_API_KEY 和 QUERIT_API_BASE_URL")
        sys.exit(1)

    api_url = base_url.rstrip("/") + search_path
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}",
    }
    payload = {"query": args.query, "num_results": args.limit}

    print(f"\n=== Querit API 响应诊断 ===")
    print(f"Query: {args.query}")
    print(f"API URL: {api_url}")
    print(f"Limit: {args.limit}")
    print()

    import requests
    try:
        resp = requests.post(api_url, json=payload, headers=headers, timeout=timeout)
    except Exception as e:
        print(f"请求失败: {type(e).__name__}: {str(e)[:200]}")
        sys.exit(1)

    print(f"HTTP 状态码: {resp.status_code}")
    print(f"Content-Type: {resp.headers.get('Content-Type', '(未知)')}")
    print()

    if resp.status_code != 200:
        print(f"非 200 响应，正文前 1000 字符:")
        print(resp.text[:1000])
        sys.exit(0)

    try:
        raw = resp.json()
    except Exception as e:
        print(f"JSON 解析失败: {e}")
        print(f"正文前 1000 字符: {resp.text[:1000]}")
        sys.exit(1)

    print(f"顶层类型: {_describe_type(raw)}")
    print()

    if isinstance(raw, dict):
        print("顶层字段及类型：")
        for k, v in raw.items():
            print(f"  {k!r}: {_describe_type(v)}")
        print()

        # 尝试定位结果数组
        candidates = ["results", "data", "items", "webpages", "documents",
                      "organic_results", "web_results", "search_results"]
        for candidate in candidates:
            val = raw.get(candidate)
            if val is not None:
                print(f"找到结果字段 {candidate!r}: {_describe_type(val)}")
                items = val
                # 如果 val 是 dict，尝试找下一层数组
                if isinstance(val, dict):
                    for sub_key in ["result", "results", "items", "data", "list"]:
                        if sub_key in val:
                            items = val[sub_key]
                            print(f"  嵌套字段 {sub_key!r}: {_describe_type(items)}")
                            break
                # items 仍然是 dict？继续向下找
                if isinstance(items, dict):
                    print(f"  items 仍是 dict，键: {list(items.keys())[:10]}")
                    for sub_key in ["result", "results", "items", "data", "list"]:
                        if sub_key in items:
                            items = items[sub_key]
                            print(f"  二级嵌套 {sub_key!r}: {_describe_type(items)}")
                            break
                if isinstance(items, list) and items:
                    first = items[0]
                    print(f"\n第一条结果类型: {_describe_type(first)}")
                    if isinstance(first, dict):
                        print("第一条结果字段及值（截断）：")
                        for fk, fv in first.items():
                            if any(s in fk.lower() for s in ("key", "token", "auth", "secret", "password")):
                                print(f"  {fk!r}: [已脱敏]")
                            else:
                                print(f"  {fk!r}: {_safe_truncate(fv, 120)}")
                    elif isinstance(first, str):
                        print(f"第一条结果（字符串）: {_safe_truncate(first, 200)}")
                elif isinstance(items, dict):
                    print(f"最终 items 仍是 dict，完整键: {list(items.keys())}")
                    print(_safe_truncate(items, 500))
                break
        else:
            print("未找到标准结果字段，完整结构（截断）：")
            print(_safe_truncate(raw, 1000))

    elif isinstance(raw, list):
        print(f"顶层是列表，长度: {len(raw)}")
        if raw:
            print(f"第一个元素类型: {_describe_type(raw[0])}")
            if isinstance(raw[0], dict):
                print("第一个元素字段：")
                for k, v in raw[0].items():
                    print(f"  {k!r}: {_safe_truncate(v, 120)}")
            elif isinstance(raw[0], str):
                print(f"第一个元素（字符串）: {_safe_truncate(raw[0], 200)}")

    # ── 专项日期候选字段诊断 ────────────────────────────────────
    _DATE_CANDIDATE_KEYS = (
        "published_date", "publishedDate", "published_at", "publishedAt",
        "date", "timestamp", "page_age", "pageAge",
        "publication_date", "publicationDate", "created_at", "createdAt",
        "updated_at", "updatedAt", "last_updated", "lastUpdated",
    )
    _DATE_FORBIDDEN_KEYS = {"collected_at", "fetched_at", "crawled_at", "indexed_at"}

    def _find_date_candidates(obj, prefix=""):
        found = []
        if isinstance(obj, dict):
            for k, v in obj.items():
                path = f"{prefix}.{k}" if prefix else k
                if k in _DATE_FORBIDDEN_KEYS:
                    continue
                if k in _DATE_CANDIDATE_KEYS and v:
                    found.append((path, v))
                elif isinstance(v, dict):
                    found.extend(_find_date_candidates(v, path))
        return found

    print("\n[日期候选字段诊断]")
    candidates_list = _find_date_candidates(raw)
    if candidates_list:
        for path, val in candidates_list:
            print(f"  {path}: {_safe_truncate(val, 80)}")
    else:
        print("  未找到任何疑似日期字段")

    # 显示解析器会使用哪个字段
    print("\n[adapt_result 最终映射]")
    # 模拟 _parse_single_item 的字段提取逻辑
    first_item = None
    items_list_extracted, _ = _extract_items_from_response_local(raw)
    if items_list_extracted:
        first_item = items_list_extracted[0] if isinstance(items_list_extracted[0], dict) else None
    if first_item:
        pub = (first_item.get("published_date") or first_item.get("published_at") or
               first_item.get("date") or first_item.get("timestamp") or
               first_item.get("page_age") or "")
        print(f"  raw_published_date = {pub!r}")
        print(f"  -> 将写入 rec['published_date'] = {pub!r}")
    else:
        print("  (无法提取第一条结果)")

    print()


def _extract_items_from_response_local(raw):
    """复制自 querit_client._extract_items_from_response，用于脚本诊断。"""
    if isinstance(raw, list):
        return raw, "顶层列表"
    if isinstance(raw, dict):
        results_val = raw.get("results")
        if isinstance(results_val, dict):
            result_list = results_val.get("result") or results_val.get("results") or []
            if isinstance(result_list, list):
                return result_list, "results.result"
        for key in ("results", "data", "items", "webpages", "documents"):
            val = raw.get(key)
            if isinstance(val, list):
                return val, key
            if isinstance(val, dict):
                for sub in ("result", "results", "items", "data", "list"):
                    sub_val = val.get(sub)
                    if isinstance(sub_val, list):
                        return sub_val, f"{key}.{sub}"
    return [], "未找到"


if __name__ == "__main__":
    main()
