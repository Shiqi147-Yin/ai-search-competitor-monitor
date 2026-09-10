"""Docs 实质变化检测器
通过 content_hash 对比判断页面是否发生了实质内容变化。
依赖 docs_snapshot_store 持久化快照。
"""
import hashlib
import re
from dataclasses import dataclass, field
from typing import Optional

try:
    from bs4 import BeautifulSoup as _BS
    _HAS_BS4 = True
except ImportError:
    _HAS_BS4 = False

from services.docs_snapshot_store import get_snapshot, upsert_snapshot
from services.docs_page_role_classifier import classify_docs_page_role


# ── 导航 / 公共模板清理选择器 ─────────────────────────────────
_NOISE_TAGS = ["nav", "footer", "header", "aside", "script", "style", "noscript"]
_NOISE_CLASS_PATTERNS = [
    r"nav", r"sidebar", r"menu", r"footer", r"header", r"breadcrumb",
    r"cookie", r"banner", r"announcement", r"topbar",
]


@dataclass
class ChangeDetectResult:
    url: str = ""
    update_status: str = "unknown"  # new_page/substantive_update/metadata_only/navigation_update/unchanged/first_seen/unknown
    content_hash: str = ""
    previous_hash: str = ""
    normalized_content: str = ""  # 截断版，最多 2000 字符用于调试
    change_summary: str = ""
    page_role: str = "generic"
    is_generic_page: bool = True
    error: str = ""


def _normalize_content(html: str) -> str:
    """清理 HTML，提取核心正文文本，用于 content_hash 计算。"""
    if not html:
        return ""

    if not _HAS_BS4:
        # 降级：简单去除 HTML 标签
        text = re.sub(r"<[^>]+>", " ", html)
        text = re.sub(r"\s+", " ", text)
        return text.strip()[:_MAX_NORM_LEN]

    soup = _BS(html, "html.parser")

    # 1. 移除噪声标签
    for tag in soup.find_all(_NOISE_TAGS):
        tag.decompose()

    # 2. 移除含噪声 class 的元素
    for pattern in _NOISE_CLASS_PATTERNS:
        for el in soup.find_all(class_=re.compile(pattern, re.I)):
            el.decompose()

    # 3. 优先提取语义正文容器
    main_content = (
        soup.find("main")
        or soup.find("article")
        or soup.find(attrs={"role": "main"})
        or soup.find(id=re.compile(r"content|main|article", re.I))
        or soup.find("div", class_=re.compile(r"content|main|article|prose", re.I))
        or soup.body
    )

    if main_content is None:
        return ""

    text = main_content.get_text(separator=" ", strip=True)
    # 规范化空白
    text = re.sub(r"\s+", " ", text).strip()
    return text


_MAX_NORM_LEN = 50_000
_SNIPPET_LEN = 2_000


def _compute_hash(text: str) -> str:
    return hashlib.md5(text.encode("utf-8", errors="replace")).hexdigest()


def detect_change(
    url: str,
    raw_html: str,
    competitor: str,
    source_type: str = "docs",
    title: str = "",
    lastmod: str = "",
    db_path=None,
) -> ChangeDetectResult:
    """检测 Docs 页面内容变化。

    流程：
    1. 归一化正文 → 计算 content_hash
    2. 查找历史快照
    3. 首次：update_status = first_seen（若DB无记录）或 new_page（首次系统发现）
    4. 再次：对比 hash → substantive_update / metadata_only / unchanged
    5. 写入/更新快照
    """
    result = ChangeDetectResult(url=url, update_status="unknown")

    try:
        page_role, is_generic = classify_docs_page_role(url, title)
        result.page_role = page_role
        result.is_generic_page = is_generic

        normalized = _normalize_content(raw_html)[:_MAX_NORM_LEN]
        new_hash = _compute_hash(normalized) if normalized else ""
        result.content_hash = new_hash
        result.normalized_content = normalized[:_SNIPPET_LEN]

        existing = get_snapshot(competitor, url, db_path=db_path)

        if existing is None:
            # 首次发现
            result.update_status = "new_page"
            result.change_summary = "首次系统发现此页面"
        else:
            prev_hash = existing.get("content_hash", "")
            result.previous_hash = prev_hash

            if not normalized or not new_hash:
                # 无法获取正文（可能反爬/SPA）
                result.update_status = "unknown"
                result.change_summary = "无法获取正文，跳过对比"
            elif new_hash == prev_hash:
                result.update_status = "unchanged"
                result.change_summary = "正文内容与上次快照一致"
            else:
                # hash 不同，进一步判断是否只是导航/元数据变化
                # 简单策略：若正文相似度极高则视为 metadata_only；否则 substantive_update
                # 当前版本：有 hash 差异即视为 substantive_update（保守策略，避免漏报）
                result.update_status = "substantive_update"
                result.change_summary = "正文内容发生变化"

        # 写入/更新快照
        upsert_snapshot(
            competitor=competitor,
            source_url=url,
            source_type=source_type,
            page_role=page_role,
            title=title,
            content_hash=new_hash,
            normalized_content=normalized,
            update_status=result.update_status,
            updated_at=lastmod,
            raw_metadata={"lastmod": lastmod, "title": title},
            db_path=db_path,
        )

    except Exception as e:
        result.update_status = "unknown"
        result.error = f"{type(e).__name__}: {str(e)[:120]}"

    return result
