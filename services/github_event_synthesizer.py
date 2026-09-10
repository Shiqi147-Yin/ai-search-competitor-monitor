"""GitHub Business Event Synthesizer
将 raw GitHub records 合成为业务级更新事件。
支持多种 provider（mock / openai / anthropic），本版本只实现 mock。
Mock 模式基于 topic-based 规则模拟 LLM 合成行为，用于测试和验证。
"""
import json
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

from services.github_event_aggregator import (
    aggregate_commits, _classify_topic, MAINTENANCE_TOPICS, GitHubAggregatedEvent,
)
from services.github_monitor import GitHubCommitRecord, GitHubReleaseRecord
from services.github_relevance_scorer import filter_events_by_relevance


# ── 业务事件数据结构 ────────────────────────────────────────────

@dataclass
class GithubBusinessEvent:
    event_id: str = ""
    competitor: str = ""
    event_title: str = ""
    event_date: str = ""
    event_type: str = "product_capability"  # product_capability/api_change/sdk_release/integration/agent_capability/developer_experience
    category: str = ""
    importance: str = "medium"
    summary: str = ""
    key_changes: list = field(default_factory=list)
    developer_impact: str = ""
    business_relevance: str = ""
    repository: str = ""
    repositories: list = field(default_factory=list)
    evidence_record_ids: list = field(default_factory=list)
    evidence_urls: list = field(default_factory=list)
    evidence_count: int = 0
    confidence: float = 0.8
    synthesis_method: str = "mock_llm_synthesis"  # mock_llm_synthesis / llm_synthesis / deterministic_release
    is_release: bool = False


@dataclass
class SynthesisResult:
    events: list = field(default_factory=list)       # list[GithubBusinessEvent]
    filtered_records: list = field(default_factory=list)  # low-value records excluded
    synthesis_status: str = "success"                 # success / fallback / failed
    provider_used: str = "mock"
    raw_record_count: int = 0
    pre_filtered_count: int = 0
    final_event_count: int = 0
    error: str = ""


# ── Pre-filter：确定性过滤低价值记录 ──────────────────────────────

_LOW_VALUE_PATTERNS = re.compile(
    r"(^merge\s|^ci:|^test:|typo|whitespace|formatting|prettier|"
    r"drop\s+unused|add\s+npm\s+publish|pin\s+publish\s+workflow|"
    r"reformat\s+typescript|gate\s+ci|format:check|"
    r"dockerfile|docker\s+cleanup|unused\s+docs|bump\s+version\s+across)",
    re.IGNORECASE,
)

_MERGE_PATTERN = re.compile(r"^Merge (pull request|branch|remote|tag)", re.IGNORECASE)


def _is_low_value(commit_title: str, topic: str) -> tuple[bool, str]:
    """判断 raw commit 是否应该被预过滤（不进入 LLM）。"""
    if _MERGE_PATTERN.match(commit_title.strip()):
        return True, "merge_commit"
    if topic in MAINTENANCE_TOPICS:
        if _LOW_VALUE_PATTERNS.search(commit_title):
            return True, f"maintenance_pattern: topic={topic}"
    return False, ""


# ── Mock LLM Provider ───────────────────────────────────────────

class MockLLMProvider:
    """Mock LLM provider，模拟 LLM 基于 topic 合成业务事件。
    不调用任何外部 API，用于测试和 CI。
    后续替换为 OpenAIProvider / AnthropicProvider 时接口保持不变。
    """

    def synthesize(
        self,
        competitor: str,
        records: list[dict],
        window_start: str,
        window_end: str,
        competitor_context: str = "",
    ) -> list[dict]:
        """模拟 LLM 合成，返回业务事件 dict 列表。
        
        每条 dict 包含：
        event_title, event_type, category, importance,
        summary, key_changes, developer_impact, business_relevance,
        repositories, evidence_record_ids, confidence
        """
        # 按 topic 分组
        by_topic: dict[str, list[dict]] = {}
        for rec in records:
            t = rec.get("topic", "other")
            by_topic.setdefault(t, []).append(rec)

        events = []
        for topic, recs in by_topic.items():
            if topic == "sdk_release":
                # 按 (repo, version) 分组
                ver_groups: dict[str, list[dict]] = {}
                for r in recs:
                    ver = re.search(r"(v?\d+\.\d+[\.\d]*)", r.get("title", ""))
                    ver_key = ver.group(1) if ver else "unknown"
                    repo_short = r.get("repository", "").split("/")[-1]
                    key = f"{repo_short}:{ver_key}"
                    ver_groups.setdefault(key, []).append(r)

                for key, group in ver_groups.items():
                    repo_short, ver = key.rsplit(":", 1) if ":" in key else (key, "")
                    from services.github_final_events import _REPO_SDK_NAMES
                    sdk_name = _REPO_SDK_NAMES.get(repo_short, repo_short)
                    events.append({
                        "event_title": f"{sdk_name} 发布 {ver}",
                        "event_type": "sdk_release",
                        "category": "产品与功能",
                        "importance": "medium",
                        "summary": f"{sdk_name} 发布版本 {ver}，包含 {len(group)} 个相关提交。",
                        "key_changes": [r.get("title", "") for r in group[:5]],
                        "developer_impact": f"使用 {sdk_name} 的开发者需更新依赖版本。",
                        "business_relevance": "SDK 版本发布，跟踪竞品 SDK 演进节奏。",
                        "repositories": list({r.get("repository", "") for r in group}),
                        "evidence_record_ids": [r.get("record_id", "") for r in group],
                        "confidence": 0.95,
                    })

            elif topic == "agent_runtime":
                all_repos = list({r.get("repository", "") for r in recs})
                events.append({
                    "event_title": f"{competitor} updates agent_run and streaming capabilities",
                    "event_type": "agent_capability",
                    "category": "生态与集成",
                    "importance": "high",
                    "summary": (
                        f"{competitor} made {len(recs)} changes to agent execution semantics: "
                        f"streaming agent_run, max-effort budgets, and heartbeat progress."
                    ),
                    "key_changes": [r.get("title", "") for r in recs[:5]],
                    "developer_impact": "Agent execution API semantics changed; developers using agent_run should review streaming/budget parameters.",
                    "business_relevance": "Agent runtime capabilities are increasingly important for AI search agent integrations.",
                    "repositories": all_repos,
                    "evidence_record_ids": [r.get("record_id", "") for r in recs],
                    "confidence": 0.85,
                })

            elif topic == "oauth_connector":
                all_repos = list({r.get("repository", "") for r in recs})
                events.append({
                    "event_title": f"{competitor} improves OAuth support for Connector distribution",
                    "event_type": "integration",
                    "category": "生态与集成",
                    "importance": "medium",
                    "summary": f"{len(recs)} OAuth/Connector-related changes merged.",
                    "key_changes": [r.get("title", "") for r in recs[:5]],
                    "developer_impact": "OAuth token forwarding and protected-resource metadata handling updated for Connector users.",
                    "business_relevance": "Connector OAuth improvements affect third-party integration distribution.",
                    "repositories": all_repos,
                    "evidence_record_ids": [r.get("record_id", "") for r in recs],
                    "confidence": 0.8,
                })

            elif topic == "crawl_api":
                all_repos = list({r.get("repository", "") for r in recs})
                events.append({
                    "event_title": f"{competitor} Crawl API deprecates start_crawl_date and end_crawl_date",
                    "event_type": "api_change",
                    "category": "产品与功能",
                    "importance": "high",
                    "summary": "start_crawl_date and end_crawl_date parameters marked as deprecated in the Crawl API.",
                    "key_changes": [r.get("title", "") for r in recs[:5]],
                    "developer_impact": "Applications using start_crawl_date or end_crawl_date should migrate before next major version.",
                    "business_relevance": "Crawl API deprecations signal direction change in date-filtering approach.",
                    "repositories": all_repos,
                    "evidence_record_ids": [r.get("record_id", "") for r in recs],
                    "confidence": 0.9,
                })

            elif topic == "sdk_api_change":
                all_repos = list({r.get("repository", "") for r in recs})
                events.append({
                    "event_title": f"{competitor} SDK updates Category enum to accept string values at runtime",
                    "event_type": "api_change",
                    "category": "产品与功能",
                    "importance": "medium",
                    "summary": f"Category values updated across Python and JavaScript SDKs to accept string input at runtime.",
                    "key_changes": [r.get("title", "") for r in recs[:5]],
                    "developer_impact": "Category parameter now accepts both enum and string values; improves flexibility.",
                    "business_relevance": "SDK type system changes affect developer ergonomics.",
                    "repositories": all_repos,
                    "evidence_record_ids": [r.get("record_id", "") for r in recs],
                    "confidence": 0.85,
                })

            elif topic in ("developer_tooling", "mcp_integration", "search_api", "contents_api"):
                all_repos = list({r.get("repository", "") for r in recs})
                topic_label = topic.replace("_", " ").title()
                events.append({
                    "event_title": f"{competitor} {topic_label} updates",
                    "event_type": "developer_experience",
                    "category": "生态与集成",
                    "importance": "low",
                    "summary": f"{len(recs)} {topic_label} changes.",
                    "key_changes": [r.get("title", "") for r in recs[:3]],
                    "developer_impact": "",
                    "business_relevance": "",
                    "repositories": all_repos,
                    "evidence_record_ids": [r.get("record_id", "") for r in recs],
                    "confidence": 0.6,
                })
            # maintenance / other / docs_cleanup → skip (already pre-filtered)
            # "other" topic with meaningful titles → generate a generic event
            elif topic == "other":
                all_repos = list({r.get("repository", "") for r in recs})
                events.append({
                    "event_title": f"{competitor} GitHub updates ({len(recs)} commits)",
                    "event_type": "product_capability",
                    "category": "产品与功能",
                    "importance": "medium",
                    "summary": "; ".join(r.get("title", "")[:80] for r in recs[:3]),
                    "key_changes": [r.get("title", "") for r in recs],
                    "developer_impact": "",
                    "business_relevance": "",
                    "repositories": all_repos,
                    "evidence_record_ids": [r.get("record_id", "") for r in recs],
                    "confidence": 0.6,
                })

        return events


class OpenAIProvider:
    """OpenAI LLM provider placeholder — 未实现，接口预留。"""

    def __init__(self, api_key: str = "", model: str = "gpt-4o-mini"):
        self.api_key = api_key
        self.model = model

    def synthesize(self, competitor, records, window_start, window_end, competitor_context="") -> list[dict]:
        raise NotImplementedError("OpenAI provider not yet implemented. Set GITHUB_SYNTHESIS_PROVIDER=mock to use mock mode.")


class AnthropicProvider:
    """Anthropic LLM provider placeholder — 未实现，接口预留。"""

    def __init__(self, api_key: str = "", model: str = "claude-3-haiku-20240307"):
        self.api_key = api_key
        self.model = model

    def synthesize(self, competitor, records, window_start, window_end, competitor_context="") -> list[dict]:
        raise NotImplementedError("Anthropic provider not yet implemented. Set GITHUB_SYNTHESIS_PROVIDER=mock to use mock mode.")


def _get_provider(provider_name: str = "mock"):
    if provider_name == "mock":
        return MockLLMProvider()
    elif provider_name == "openai":
        import os
        return OpenAIProvider(api_key=os.environ.get("OPENAI_API_KEY", ""))
    elif provider_name == "anthropic":
        import os
        return AnthropicProvider(api_key=os.environ.get("ANTHROPIC_API_KEY", ""))
    else:
        return MockLLMProvider()


# ── 主合成函数 ──────────────────────────────────────────────────

def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def synthesize_github_events(
    competitor: str,
    raw_commits: list[GitHubCommitRecord],
    raw_releases: list[GitHubReleaseRecord],
    window_start: str,
    window_end: str,
    competitor_context: str = "",
    provider_name: str = "mock",
    config_keywords: dict = None,
) -> SynthesisResult:
    """合成 GitHub 业务事件。

    流程：
    1. 确定性预过滤：移除 merge commit / low-value records
    2. 构建标准化 records list（包含 topic 标签）
    3. SDK Release 确定性预聚合（不进 LLM）
    4. 其余 records 传入 LLM provider 合成
    5. 校验 evidence IDs、过滤无证据事件
    6. LLM 失败时降级到 deterministic aggregator
    7. 返回 SynthesisResult
    """
    result = SynthesisResult(
        raw_record_count=len(raw_commits) + len(raw_releases),
        provider_used=provider_name,
    )

    filtered_records = []
    llm_candidate_records = []

    # ── 1. 预过滤 raw commits ──────────────────────────────────
    record_map: dict[str, dict] = {}  # record_id → record
    rid = 0

    # Release records → 先确定性处理
    for rel in raw_releases:
        rid += 1
        rec_id = f"release_{rid}"
        rec = {
            "record_id": rec_id,
            "type": "release",
            "repository": rel.repository,
            "title": rel.release_title or f"Release {rel.version}",
            "date": rel.published_at,
            "url": rel.release_url,
            "topic": "sdk_release",
            "version": rel.version,
            "summary": rel.release_notes[:200] if rel.release_notes else "",
        }
        record_map[rec_id] = rec
        llm_candidate_records.append(rec)

    for commit in raw_commits:
        rid += 1
        rec_id = f"commit_{rid}"
        topic = _classify_topic(commit.commit_title)
        is_low, reason = _is_low_value(commit.commit_title, topic)

        if is_low or _MERGE_PATTERN.match(commit.commit_title.strip()):
            filtered_records.append({
                "record_id": rec_id,
                "type": "commit",
                "title": commit.commit_title,
                "repository": commit.repository,
                "date": commit.commit_date,
                "url": commit.commit_url,
                "topic": topic,
                "filter_reason": reason or "merge_commit",
            })
            result.filtered_records.append(commit.commit_title[:80])
            continue

        rec = {
            "record_id": rec_id,
            "type": "commit",
            "repository": commit.repository,
            "title": commit.commit_title,
            "date": commit.commit_date,
            "url": commit.commit_url,
            "topic": topic,
            "summary": commit.change_summary or "",
        }
        record_map[rec_id] = rec
        llm_candidate_records.append(rec)

    result.pre_filtered_count = len(filtered_records)

    # ── 2. 调用 provider ──────────────────────────────────────
    try:
        provider = _get_provider(provider_name)
        raw_events = provider.synthesize(
            competitor=competitor,
            records=llm_candidate_records,
            window_start=window_start,
            window_end=window_end,
            competitor_context=competitor_context,
        )
        synthesis_method = "mock_llm_synthesis" if provider_name == "mock" else "llm_synthesis"
        result.synthesis_status = "success"

    except Exception as e:
        # ── Fallback to deterministic aggregator ────────────────
        result.synthesis_status = "fallback"
        result.error = str(e)[:200]
        agg_events = aggregate_commits(raw_commits)
        primary, _ = filter_events_by_relevance(agg_events, config_keywords=config_keywords)
        fallback_events = []
        for ev in primary:
            fallback_events.append(GithubBusinessEvent(
                event_id=f"fallback_{len(fallback_events)+1}",
                competitor=competitor,
                event_title=ev.event_title,
                event_date=ev.start_date,
                event_type=ev.topic if hasattr(ev, "topic") else "product_capability",
                summary=ev.summary,
                key_changes=ev.key_changes,
                repository=ev.repository,
                repositories=[ev.repository],
                evidence_record_ids=[],
                evidence_urls=ev.commit_urls,
                evidence_count=ev.commit_count,
                synthesis_method="deterministic_fallback",
                is_release=ev.is_release,
            ))
        result.events = fallback_events
        result.final_event_count = len(fallback_events)
        return result

    # ── 3. 校验 evidence IDs 并构建 GithubBusinessEvent ────────
    valid_record_ids = set(record_map.keys())
    business_events = []

    for i, ev_dict in enumerate(raw_events):
        ev_ids = ev_dict.get("evidence_record_ids", [])
        # 过滤无效 ID（防止幻觉）
        valid_ids = [eid for eid in ev_ids if eid in valid_record_ids]
        if not valid_ids:
            # 没有任何有效 evidence → 丢弃
            continue

        evidence_urls = []
        ev_repos = set()
        for eid in valid_ids:
            rec = record_map.get(eid, {})
            url = rec.get("url", "")
            if url:
                evidence_urls.append(url)
            repo = rec.get("repository", "")
            if repo:
                ev_repos.add(repo)

        date = min(
            (record_map[eid].get("date", "") for eid in valid_ids if record_map.get(eid, {}).get("date")),
            default="",
        )

        be = GithubBusinessEvent(
            event_id=f"be_{i+1:03d}",
            competitor=competitor,
            event_title=ev_dict.get("event_title", "GitHub Update"),
            event_date=date,
            event_type=ev_dict.get("event_type", "product_capability"),
            category=ev_dict.get("category", ""),
            importance=ev_dict.get("importance", "medium"),
            summary=ev_dict.get("summary", ""),
            key_changes=ev_dict.get("key_changes", []),
            developer_impact=ev_dict.get("developer_impact", ""),
            business_relevance=ev_dict.get("business_relevance", ""),
            repository=list(ev_dict.get("repositories", ev_repos))[0] if ev_dict.get("repositories") else "",
            repositories=ev_dict.get("repositories") or list(ev_repos),
            evidence_record_ids=valid_ids,
            evidence_urls=evidence_urls,
            evidence_count=len(valid_ids),
            confidence=ev_dict.get("confidence", 0.7),
            synthesis_method=synthesis_method,
            is_release=ev_dict.get("event_type") == "sdk_release",
        )
        business_events.append(be)

    # 按日期排序（最新在前）
    business_events.sort(key=lambda e: e.event_date or "", reverse=True)

    result.events = business_events
    result.final_event_count = len(business_events)
    return result
