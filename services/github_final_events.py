"""GitHub Release 与 Commit 事件合并器
将 releases 与对应的 commit 聚合事件合并为统一的 final_github_events。
同版本的 release + version-bump commit 合并为一条。
不同 repo 的同版本 release 分别保留（标题标明 SDK 名称）。
"""
import re
from dataclasses import dataclass, field

from services.github_monitor import GitHubReleaseRecord
from services.github_event_aggregator import GitHubAggregatedEvent
from services.official_update_normalizer import OfficialUpdateItem

_VERSION_RE = re.compile(r"(v?\d+\.\d+[\.\d]*)")

# SDK 仓库名称映射（可扩展）
_REPO_SDK_NAMES = {
    "exa-py":          "Exa Python SDK",
    "exa-js":          "Exa JavaScript SDK",
    "exa-mcp-server":  "Exa MCP Server",
    "tavily-mcp":      "tavily-mcp",
    "tavily-python":   "Tavily Python SDK",
    "search-api-go":   "Brave Search API Go Client",
    "brave-search-skills": "Brave Search Skills",
}


def _extract_version(text: str) -> str | None:
    m = _VERSION_RE.search(text or "")
    return m.group(1) if m else None


def _repo_sdk_name(repository: str) -> str:
    repo_short = repository.split("/")[-1] if "/" in repository else repository
    return _REPO_SDK_NAMES.get(repo_short, repo_short)


def merge_releases_with_events(
    releases: list[GitHubReleaseRecord],
    commit_events: list[OfficialUpdateItem],
) -> tuple[list[OfficialUpdateItem], list[OfficialUpdateItem]]:
    """合并 Release 与对应 Commit 事件为 final_github_events。

    规则：
    1. 同 repo + 同版本的 release commit event → 合并为一条（release 优先，commit 作为 evidence）
    2. 纯 Release（没有对应 commit event）→ 转换为 OfficialUpdateItem
    3. 纯 Commit event（非 release 类型）→ 直接保留
    4. 不同 repo 同版本 → 分别保留，标题含 SDK 名称

    Returns:
        (final_events, raw_releases_as_diagnostic)
        raw_releases_as_diagnostic: 所有 raw release 归入诊断区，供审计
    """
    final_events: list[OfficialUpdateItem] = []
    consumed_release_keys: set[str] = set()  # "repo:version"

    # ── Step 1: commit events 中标记为 release 的，尝试找对应 raw release ──
    for event in commit_events:
        ver = _extract_version(event.update_title or "")
        if ver and getattr(event, "github_relevance", "") == "product_capability":
            # 这是一个 SDK release commit event
            repo = event.source_url.split("/commit/")[0].replace("https://github.com/", "") if event.source_url else ""
            release_key = f"{repo}:{ver}"

            # 找到匹配的 raw release
            matched = next(
                (r for r in releases
                 if r.repository.split("/")[-1] in event.source_url
                 and _extract_version(r.version) == ver
                 and f"{r.repository}:{r.version}" not in consumed_release_keys),
                None,
            )
            if matched:
                consumed_release_keys.add(f"{matched.repository}:{matched.version}")
                sdk_name = _repo_sdk_name(matched.repository)
                # 合并：用 release 日期（更权威），保留 commit URLs
                event.update_title = f"{sdk_name} 发布 {matched.version}"
                event.update_date = matched.published_at or event.update_date
                # 追加 release URL 到 evidence
                if matched.release_url and matched.release_url not in (event.evidence_urls or []):
                    if not event.evidence_urls:
                        event.evidence_urls = []
                    event.evidence_urls.insert(0, matched.release_url)
                    event.source_url = matched.release_url
                if matched.release_notes:
                    event.summary = event.summary or matched.release_notes[:200]
            else:
                # 没找到对应 raw release，直接使用 SDK 名称优化标题
                repo_part = event.update_title.split(":")[0] if ":" in event.update_title else ""
                if repo_part:
                    sdk_name = _repo_sdk_name(repo_part)
                    event.update_title = f"{sdk_name} 发布 {ver}"

            final_events.append(event)
        else:
            # 非 release commit event，直接保留
            final_events.append(event)

    # ── Step 2: 剩余未消费的 raw releases → 生成独立 final event ──
    for rel in releases:
        key = f"{rel.repository}:{rel.version}"
        if key not in consumed_release_keys:
            sdk_name = _repo_sdk_name(rel.repository)
            item = OfficialUpdateItem(
                competitor="",
                update_title=f"{sdk_name} 发布 {rel.version}",
                update_date=rel.published_at,
                source_channel="github_release",
                content_type="release",
                source_url=rel.release_url,
                published_at=rel.published_at,
                summary=rel.release_notes[:200] if rel.release_notes else "",
                discovery_method="official_direct",
                import_eligible=True,
                evidence_urls=[rel.release_url] if rel.release_url else [],
            )
            item.github_relevance = "product_capability"
            item.github_relevance_score = 0.6
            final_events.append(item)

    # ── Step 3: 按日期排序 ──
    final_events.sort(key=lambda e: (e.update_date or ""), reverse=True)

    return final_events, []
