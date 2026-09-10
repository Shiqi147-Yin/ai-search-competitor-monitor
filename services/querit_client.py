"""Querit API Client
职责：读取配置、发起搜索请求、处理错误、返回标准结果。
不做页面逻辑，不直接写竞品记录，不记录 API Key。

如果项目中尚未有确切的 Querit API 请求格式说明，请在使用真实 API 前：
1. 确认 QUERIT_API_BASE_URL 和 QUERIT_API_SEARCH_PATH
2. 确认请求体字段（query、num_results 等）
3. 确认响应结构（results 数组字段）
4. 更新 build_request_payload() 和 parse_search_response()
"""
import logging
import time
from dataclasses import dataclass, field
from typing import Optional

try:
    import requests as _requests
    _HAS_REQUESTS = True
except ImportError:
    _HAS_REQUESTS = False

import os as _os
from env_loader import get_env_bool


def _get_config() -> dict:
    """运行时从环境变量读取配置，使用统一布尔解析，确保 .env 变更生效。"""
    return {
        "base_url": _os.environ.get("QUERIT_API_BASE_URL", ""),
        "api_key": _os.environ.get("QUERIT_API_KEY", ""),
        "search_path": _os.environ.get("QUERIT_API_SEARCH_PATH", "/search"),
        "timeout": int(_os.environ.get("QUERIT_API_TIMEOUT", "30")),
        "max_retries": int(_os.environ.get("QUERIT_API_MAX_RETRIES", "1")),
        # 使用统一的 get_env_bool，default=True（未配置时安全地使用 Mock）
        "mock_mode": get_env_bool("QUERIT_MOCK_MODE", default=True),
    }

logger = logging.getLogger(__name__)

# 标准搜索结果结构（与原始响应解耦）
@dataclass
class SearchResult:
    title: str = ""
    url: str = ""
    content: str = ""
    summary: str = ""
    published_date: str = ""
    score: Optional[float] = None
    raw_source: str = ""
    query: str = ""
    rank: int = 0
    raw_metadata: dict = field(default_factory=dict)


@dataclass
class SearchRunResult:
    query: str = ""
    results: list = field(default_factory=list)   # list[SearchResult]
    success: bool = False
    error: str = ""
    duration_ms: int = 0
    is_mock: bool = False
    http_status: int = 0
    invalid_result_count: int = 0
    source_path: str = ""


def check_config() -> tuple[bool, str]:
    """检查 API 配置是否完整。返回 (ok, error_message)。每次调用重新读取环境变量。"""
    cfg = _get_config()
    if cfg["mock_mode"]:
        return True, ""
    if not cfg["api_key"]:
        return False, "QUERIT_API_KEY 未设置，请在环境变量中配置"
    if not cfg["base_url"]:
        return False, "QUERIT_API_BASE_URL 未设置，请在环境变量中配置"
    return True, ""


def build_request_payload(query: str, num_results: int = 10) -> dict:
    """构建请求体。
    TODO: 根据真实 Querit API 文档确认字段名。
    当前使用占位结构，真实接入前需更新。
    """
    return {
        "query": query,
        "num_results": num_results,
        # 其他字段待确认后补充，例如：
        # "search_depth": "advanced",
        # "include_domains": [],
        # "time_range": "week",
    }


def _extract_items_from_response(raw) -> tuple[list, str]:
    """从各种响应结构中提取结果列表。
    返回 (items_list, source_path_desc)。
    """
    if isinstance(raw, list):
        return raw, "顶层列表"

    if isinstance(raw, dict):
        # Querit 真实响应：{"results": {"result": [...]}}
        results_val = raw.get("results")
        if isinstance(results_val, dict):
            result_list = results_val.get("result") or results_val.get("results") or []
            if isinstance(result_list, list):
                return result_list, "results.result"

        # 常见平铺结构：{"results": [...]}
        for key in ("results", "data", "items", "webpages", "documents",
                    "organic_results", "web_results", "search_results"):
            val = raw.get(key)
            if isinstance(val, list):
                return val, key
            if isinstance(val, dict):
                # 二级嵌套
                for sub in ("result", "results", "items", "data", "list"):
                    sub_val = val.get(sub)
                    if isinstance(sub_val, list):
                        return sub_val, f"{key}.{sub}"

    return [], "未找到"


def _parse_single_item(item, rank: int, query: str) -> "SearchResult | None":
    """解析单条结果，支持 dict 和 string。
    返回 SearchResult 或 None（无效条目）。
    """
    if isinstance(item, dict):
        url = (item.get("url") or item.get("link") or item.get("source_url") or "")
        if not url:
            return None  # 无 URL，跳过

        title = (item.get("title") or item.get("name") or item.get("headline") or "")
        content = (item.get("content") or item.get("text") or
                   item.get("snippet") or item.get("description") or
                   item.get("raw_content") or "")
        summary = (item.get("summary") or item.get("snippet") or
                   item.get("description") or "")
        published_date = (item.get("published_date") or item.get("published_at") or
                          item.get("date") or item.get("timestamp") or
                          item.get("page_age") or "")
        score = (item.get("score") or item.get("relevance_score") or item.get("rank_score"))
        raw_source = item.get("source") or item.get("site_name") or item.get("domain") or ""

        # 安全构建 raw_metadata（过滤已映射字段）
        mapped_keys = {"url", "link", "source_url", "title", "name", "headline",
                       "content", "text", "snippet", "description", "raw_content",
                       "summary", "published_date", "published_at", "date",
                       "timestamp", "page_age", "score", "relevance_score",
                       "rank_score", "source", "site_name", "domain"}
        raw_metadata = {k: v for k, v in item.items() if k not in mapped_keys}

        return SearchResult(
            title=title, url=url, content=content, summary=summary,
            published_date=published_date, score=score, raw_source=raw_source,
            query=query, rank=rank, raw_metadata=raw_metadata,
        )

    if isinstance(item, str):
        # 字符串条目：尝试识别为 URL
        item_stripped = item.strip()
        if item_stripped.startswith(("http://", "https://")):
            return SearchResult(
                url=item_stripped, query=query, rank=rank,
                raw_metadata={"_item_was_string": True},
            )
        # 普通文本字符串，无法提取 URL，跳过
        return None

    return None  # 其他类型，跳过


def parse_search_response(raw, query: str) -> tuple[list, int, str]:
    """将原始 API 响应解析为标准结果列表。

    Returns: (results: list[SearchResult], invalid_count: int, source_path: str)
    """
    results: list[SearchResult] = []
    invalid_count = 0

    items, source_path = _extract_items_from_response(raw)

    for rank, item in enumerate(items, start=1):
        try:
            parsed = _parse_single_item(item, rank, query)
            if parsed is not None:
                results.append(parsed)
            else:
                invalid_count += 1
        except Exception:
            invalid_count += 1
            # 单条解析失败不中断整体

    return results, invalid_count, source_path


def _load_mock_results(query: str, num_results: int) -> list[SearchResult]:
    """从 fixtures 读取 Mock 数据。"""
    import json
    from pathlib import Path
    fixture = Path(__file__).parent.parent / "tests" / "fixtures" / "querit_search_response.json"
    if fixture.exists():
        try:
            raw = json.loads(fixture.read_text(encoding="utf-8"))
            items = raw.get("results", [])[:num_results]
            results, _, _ = parse_search_response({"results": items}, query)
            return results
        except Exception:
            pass
    # 内置最小 mock
    return [
        SearchResult(
            title=f"[MOCK] {query[:40]} — result 1",
            url="https://mock.example.com/result1",
            content="This is mock content for testing purposes.",
            summary="Mock summary for Querit API test.",
            published_date="2026-07-20",
            score=0.95,
            query=query,
            rank=1,
        ),
        SearchResult(
            title=f"[MOCK] {query[:40]} — result 2",
            url="https://mock.example.com/result2",
            content="Second mock result content.",
            summary="Another mock result.",
            published_date="2026-07-19",
            score=0.88,
            query=query,
            rank=2,
        ),
    ]


def search(query: str, num_results: int = 10) -> SearchRunResult:
    """执行一次搜索，返回 SearchRunResult。每次调用重新读取环境变量以支持测试。"""
    start = time.time()
    cfg = _get_config()

    if cfg["mock_mode"]:
        mock_results = _load_mock_results(query, num_results)
        duration = int((time.time() - start) * 1000)
        return SearchRunResult(
            query=query, results=mock_results,
            success=True, duration_ms=duration, is_mock=True,
        )

    ok, err = check_config()
    if not ok:
        return SearchRunResult(query=query, error=err, success=False)

    if not _HAS_REQUESTS:
        return SearchRunResult(query=query, error="requests 库未安装", success=False)

    api_url = cfg["base_url"].rstrip("/") + cfg["search_path"]
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {cfg['api_key']}",
    }
    payload = build_request_payload(query, num_results)

    for attempt in range(1 + cfg["max_retries"]):
        try:
            resp = _requests.post(
                api_url, json=payload, headers=headers,
                timeout=cfg["timeout"],
            )
            duration = int((time.time() - start) * 1000)

            if resp.status_code == 200:
                try:
                    raw = resp.json()
                except Exception as e:
                    return SearchRunResult(
                        query=query,
                        error=f"响应 JSON 解析失败：{e}",
                        success=False,
                        duration_ms=duration,
                        http_status=resp.status_code,
                    )
                results = parse_search_response(raw, query)
                parsed_list, invalid_count, source_path = results
                return SearchRunResult(
                    query=query,
                    results=parsed_list,
                    success=True,
                    duration_ms=duration,
                    http_status=resp.status_code,
                    invalid_result_count=invalid_count,
                    source_path=source_path,
                )
            elif resp.status_code in (401, 403):
                return SearchRunResult(
                    query=query,
                    error=f"认证失败（HTTP {resp.status_code}），请检查 QUERIT_API_KEY",
                    success=False,
                    duration_ms=duration,
                    http_status=resp.status_code,
                )
            elif resp.status_code == 429:
                return SearchRunResult(
                    query=query,
                    error=f"API 请求频率超限（HTTP 429），请稍后重试",
                    success=False,
                    duration_ms=duration,
                    http_status=resp.status_code,
                )
            elif resp.status_code >= 500:
                if attempt < cfg["max_retries"]:
                    time.sleep(1)
                    continue
                return SearchRunResult(
                    query=query,
                    error=f"服务端错误（HTTP {resp.status_code}）",
                    success=False,
                    duration_ms=duration,
                    http_status=resp.status_code,
                )
            else:
                return SearchRunResult(
                    query=query,
                    error=f"HTTP {resp.status_code}",
                    success=False,
                    duration_ms=duration,
                    http_status=resp.status_code,
                )

        except _requests.exceptions.Timeout:
            if attempt < cfg["max_retries"]:
                time.sleep(1)
                continue
            duration = int((time.time() - start) * 1000)
            return SearchRunResult(
                query=query, error="请求超时", success=False, duration_ms=duration
            )
        except _requests.exceptions.ConnectionError as e:
            duration = int((time.time() - start) * 1000)
            return SearchRunResult(
                query=query,
                error=f"连接错误：{str(e)[:80]}",
                success=False,
                duration_ms=duration,
            )
        except Exception as e:
            duration = int((time.time() - start) * 1000)
            return SearchRunResult(
                query=query,
                error=f"{type(e).__name__}: {str(e)[:80]}",
                success=False,
                duration_ms=duration,
            )

    duration = int((time.time() - start) * 1000)
    return SearchRunResult(query=query, error="重试耗尽", success=False, duration_ms=duration)


def is_mock_mode() -> bool:
    """运行时检查当前是否为 Mock 模式（每次调用重新读取环境变量）。"""
    return get_env_bool("QUERIT_MOCK_MODE", default=True)


# 向后兼容：模块级常量在导入时快照，仅用于兼容旧代码
# 推荐使用 is_mock_mode() 函数以获得运行时最新值
QUERIT_MOCK_MODE = is_mock_mode()
