"""GitHub 事件聚合器 V3：业务主题级聚合
在 V2 基础上增加：
1. 业务主题分类（topic）
2. 跨 repo 同主题聚合（agent_runtime、sdk_api_change、crawl_api 等）
3. 低价值事件前置过滤（maintenance/docs_cleanup/internal_refactor）
4. 业务化事件标题生成

不修改抓取层，只改聚合逻辑。
"""
import re
from dataclasses import dataclass, field
from datetime import datetime

from services.github_monitor import GitHubCommitRecord

# Merge commit 过滤
_MERGE_PATTERN = re.compile(
    r"^Merge (pull request|branch|remote|tag)",
    re.IGNORECASE,
)

# Release/version-bump 模式
_RELEASE_PATTERN = re.compile(
    r"(chore[:\(].*release|release\s+v?\d+\.\d+|bump\s+version|version\s+bump|"
    r"chore\(master\).*release|prepare\s+release|cut\s+release|"
    r"chore:\s*release|release:\s*v?\d)",
    re.IGNORECASE,
)

# PR reference pattern
_PR_PATTERN = re.compile(r"\(#(\d+)\)|\s#(\d+)")

# 版本号提取
_VERSION_RE = re.compile(r"(v?\d+\.\d+[\.\d]*)")

# 停词（扩展版）
_STOP_WORDS = {
    "a", "an", "the", "and", "or", "but", "in", "on", "at", "to",
    "for", "of", "with", "by", "from", "up", "as", "into", "is",
    "fix", "add", "update", "remove", "refactor", "bump", "chore",
    "feat", "docs", "test", "style", "build", "revert", "ci", "perf",
}

# ── 业务主题分类规则 ──────────────────────────────────────────
_TOPIC_RULES = [
    # sdk_release 必须最先匹配
    ("sdk_release", re.compile(
        r"(chore.*release|release\s+v?\d+|version\s+bump|bump\s+version|"
        r"release-please|prepare.release|cut.release|tag.release)",
        re.IGNORECASE,
    )),
    # maintenance / ci 前置过滤（在具体功能规则之前）
    ("maintenance", re.compile(
        r"(^pin\s|prettier|lint|format|ci\s|github.action|workflow|"
        r"dependency|typo|whitespace|reformat|deploy\s|".strip() +
        r"drop\s+unused|remove\s+unused|cleanup|clean.up|"
        r"dockerfile|docker|whoami|publish.workflow|npm.publish)",
        re.IGNORECASE,
    )),
    # agent_runtime
    ("agent_runtime", re.compile(
        r"(agent.run|agent_run|agent.tool|streaming.agent|"
        r"max.effort|heartbeat|resumable|agent.plugin|agent.cap)",
        re.IGNORECASE,
    )),
    # oauth_connector
    ("oauth_connector", re.compile(
        r"(oauth|connector|protected.resource|login.*challenge|"
        r"forward.*token|bearer|auth.*token)",
        re.IGNORECASE,
    )),
    # mcp_integration
    ("mcp_integration", re.compile(
        r"(mcp|model.context.protocol|\bmcp\b)",
        re.IGNORECASE,
    )),
    # crawl_api
    ("crawl_api", re.compile(
        r"(crawl.date|start_crawl|end_crawl|crawl.param|crawl.api|"
        r"deprecated.*crawl|crawl.*deprecated)",
        re.IGNORECASE,
    )),
    # search_api
    ("search_api", re.compile(
        r"(search.api|search.param|neural.search|semantic.search|"
        r"search.result|search.endpoint)",
        re.IGNORECASE,
    )),
    # sdk_api_change (catch-all for API params)
    ("sdk_api_change", re.compile(
        r"(category.value|accept.str|category.enum|deprecated.*param|"
        r"api.param|type.fix|runtime.type)",
        re.IGNORECASE,
    )),
    # developer_tooling (docs/readme)
    ("developer_tooling", re.compile(
        r"(readme|documentation|install.guide|getting.started|"
        r"rewrite.readme|clearer.install)",
        re.IGNORECASE,
    )),
    # docs_cleanup
    ("docs_cleanup", re.compile(
        r"(drop.docs|remove.docs|clean.docs|unused.docs)",
        re.IGNORECASE,
    )),
]

# Topics that should be filtered to diagnostics (not final events)
MAINTENANCE_TOPICS = {
    "maintenance", "docs_cleanup", "internal_refactor",
}

# Topics that MUST have explicit API/capability change to be primary
REQUIRES_PUBLIC_SIGNAL = {
    "developer_tooling",  # README update alone is not high-value
}


def _classify_topic(title: str) -> str:
    for topic, pattern in _TOPIC_RULES:
        if pattern.search(title):
            return topic
    return "other"


def _extract_pr_number(title: str) -> str | None:
    m = _PR_PATTERN.search(title)
    return m.group(1) or m.group(2) if m else None


def _is_merge_commit(title: str) -> bool:
    return bool(_MERGE_PATTERN.match(title.strip()))


def _extract_keywords(title: str) -> set[str]:
    words = re.findall(r"[a-zA-Z][a-zA-Z0-9_-]{1,}", title.lower())
    return {w for w in words if w not in _STOP_WORDS and len(w) > 2}


def _keyword_overlap(title_a: str, title_b: str) -> float:
    kw_a = _extract_keywords(title_a)
    kw_b = _extract_keywords(title_b)
    if not kw_a or not kw_b:
        return 0.0
    return len(kw_a & kw_b) / len(kw_a | kw_b)


def _parse_date(date_str: str):
    if not date_str:
        return None
    try:
        return datetime.strptime(date_str[:10], "%Y-%m-%d").date()
    except Exception:
        return None


def _infer_category(titles: list[str]) -> str:
    combined = " ".join(titles).lower()
    if any(w in combined for w in ("deprecated", "deprecate", "breaking", "removed")):
        return "sdk_api_change"
    if any(w in combined for w in ("fix", "bug", "error", "crash")):
        return "bugfix"
    if any(w in combined for w in ("doc", "readme", "changelog")):
        return "docs"
    if any(w in combined for w in ("ci", "workflow", "infra")):
        return "infra"
    if any(w in combined for w in ("config", "version", "dependency")):
        return "config"
    return "feature"


_REPO_SDK_NAMES = {
    "exa-py":        "Exa Python SDK",
    "exa-js":        "Exa JavaScript SDK",
    "exa-mcp-server": "Exa MCP Server",
    "tavily-mcp":    "tavily-mcp",
    "tavily-python": "Tavily Python SDK",
}

_TOPIC_TITLE_TEMPLATES = {
    "agent_runtime": "Exa updates agent_run and streaming capabilities",
    "oauth_connector": "Exa updates OAuth support for Connector distribution",
    "mcp_integration": "Exa MCP Server integration updates",
    "crawl_api": "Exa Crawl API parameter changes",
    "search_api": "Exa Search API updates",
    "sdk_api_change": "Exa SDK API parameter fixes",
    "developer_tooling": "Exa developer documentation updates",
}


def _generate_topic_title(topic: str, commits: list[GitHubCommitRecord], repo: str) -> str:
    repo_short = repo.split("/")[-1] if "/" in repo else repo
    sdk_name = _REPO_SDK_NAMES.get(repo_short, repo_short)

    # sdk_release: use version number
    if topic == "sdk_release":
        ver = None
        for c in commits:
            m = _VERSION_RE.search(c.commit_title)
            if m:
                ver = m.group(1)
                break
        if ver:
            return f"{sdk_name} 发布 {ver}"
        return f"{sdk_name} release"

    # Topic template
    if topic in _TOPIC_TITLE_TEMPLATES:
        # cross-repo: don't prefix repo name
        if len({c.repository for c in commits}) > 1:
            return _TOPIC_TITLE_TEMPLATES[topic]
        return f"{sdk_name}: {_TOPIC_TITLE_TEMPLATES[topic].split('Exa ')[-1]}"

    # Fallback
    if len(commits) == 1:
        clean = _PR_PATTERN.sub("", commits[0].commit_title).strip()
        return clean[:100]
    return f"{sdk_name}: {topic.replace('_', ' ')} updates"


@dataclass
class GitHubAggregatedEvent:
    event_title: str = ""
    repository: str = ""
    start_date: str = ""
    end_date: str = ""
    commit_count: int = 0
    commit_urls: list = field(default_factory=list)
    changed_files: list = field(default_factory=list)
    summary: str = ""
    key_changes: list = field(default_factory=list)
    developer_impact: str = ""
    category: str = "feature"
    importance: str = "medium"
    is_release: bool = False
    topic: str = "other"


def aggregate_commits(
    commits: list[GitHubCommitRecord],
    time_window_days: int = 7,
    overlap_threshold: float = 0.2,
) -> list[GitHubAggregatedEvent]:
    """业务主题级聚合 V3。

    流程：
    1. 过滤 Merge commit
    2. 每条 commit 分类到业务主题（topic）
    3. maintenance/docs_cleanup → 直接归为诊断组（不进 final events）
    4. 同 repo + 同 topic 或 同 PR → 聚合
    5. 跨 repo 同 topic（如 agent_runtime）→ 聚合为一个 final event
    6. 生成业务化标题
    """
    # 1. 过滤 merge commits
    functional = [c for c in commits if not _is_merge_commit(c.commit_title)]

    # 2. 为每条 commit 打 topic 标签
    classified: list[tuple[str, GitHubCommitRecord]] = [
        (_classify_topic(c.commit_title), c) for c in functional
    ]

    # 3. 分离 maintenance（直接到诊断）
    # maintenance 只有在进入 diagnostics 后通过 filter_events_by_relevance 处理
    # 这里先按 topic 分组（含 maintenance，后续由 relevance_scorer 过滤）

    # 4. 按 (repo, topic) 分组，再同 topic 跨 repo 合并
    # 先按 topic 归组（不限 repo，跨 repo 同 topic 可合并）
    by_topic: dict[str, list[GitHubCommitRecord]] = {}
    for topic, c in classified:
        by_topic.setdefault(topic, []).append(c)

    events: list[GitHubAggregatedEvent] = []

    for topic, topic_commits in by_topic.items():
        topic_commits.sort(key=lambda c: c.commit_date or "")

        # sdk_release: 按 (repo, version) 分组
        if topic == "sdk_release":
            ver_repo_groups: dict[str, list[GitHubCommitRecord]] = {}
            for c in topic_commits:
                ver = None
                m = _VERSION_RE.search(c.commit_title)
                if m:
                    ver = m.group(1)
                repo_short = c.repository.split("/")[-1]
                key = f"{repo_short}:{ver}" if ver else f"{repo_short}:unknown"
                ver_repo_groups.setdefault(key, []).append(c)

            for key, group in ver_repo_groups.items():
                dates = [c.commit_date for c in group if c.commit_date]
                repo = group[0].repository
                events.append(GitHubAggregatedEvent(
                    event_title=_generate_topic_title("sdk_release", group, repo),
                    repository=repo,
                    start_date=min(dates) if dates else "",
                    end_date=max(dates) if dates else "",
                    commit_count=len(group),
                    commit_urls=[c.commit_url for c in group if c.commit_url],
                    changed_files=[],
                    summary="; ".join(c.commit_title for c in group[:3]),
                    key_changes=[c.commit_title for c in group],
                    category="config",
                    importance="medium",
                    is_release=True,
                    topic=topic,
                ))
            continue

        # 其他 topic: 分 PR 组，再时间+关键词组
        pr_groups: dict[str, list[GitHubCommitRecord]] = {}
        no_pr: list[GitHubCommitRecord] = []
        for c in topic_commits:
            pr = _extract_pr_number(c.commit_title)
            if pr:
                pr_groups.setdefault(f"pr_{pr}", []).append(c)
            else:
                no_pr.append(c)

        all_groups: list[list[GitHubCommitRecord]] = list(pr_groups.values())

        # 同一 topic 的无 PR commit → 整个 topic 时间窗口内合并为尽可能少的组
        # 对于 agent_runtime / sdk_api_change 等高聚合主题，扩大窗口到全部时间
        is_high_cohesion_topic = topic in (
            "agent_runtime", "oauth_connector", "mcp_integration",
            "crawl_api", "search_api", "sdk_api_change",
        )
        effective_window = time_window_days * 4 if is_high_cohesion_topic else time_window_days

        if no_pr:
            time_groups: list[list[GitHubCommitRecord]] = []
            for c in no_pr:
                merged = False
                c_dt = _parse_date(c.commit_date)
                for g in time_groups:
                    for ex in g:
                        ex_dt = _parse_date(ex.commit_date)
                        days = abs((c_dt - ex_dt).days) if c_dt and ex_dt else 999
                        if days <= effective_window:
                            g.append(c)
                            merged = True
                            break
                    if merged:
                        break
                if not merged:
                    time_groups.append([c])
            all_groups.extend(time_groups)

        # 对于高内聚主题：合并所有 PR 组和无 PR 组（同主题就是同事件）
        if is_high_cohesion_topic and len(all_groups) > 1:
            # 把所有组合并为一个（跨 PR 同主题聚合）
            merged_group = [c for g in all_groups for c in g]
            all_groups = [merged_group]

        for group in all_groups:
            dates = [c.commit_date for c in group if c.commit_date]
            all_files = [f for c in group for f in c.changed_files]
            titles = [c.commit_title for c in group]
            # 跨 repo → 用 "exa-labs" 作为 repo 标识
            repo = group[0].repository if len({c.repository for c in group}) == 1 else "exa-labs"
            events.append(GitHubAggregatedEvent(
                event_title=_generate_topic_title(topic, group, repo),
                repository=repo,
                start_date=min(dates) if dates else "",
                end_date=max(dates) if dates else "",
                commit_count=len(group),
                commit_urls=[c.commit_url for c in group if c.commit_url],
                changed_files=list(dict.fromkeys(all_files)),
                summary="; ".join(titles[:5]),
                key_changes=titles,
                category=_infer_category(titles),
                importance="high" if len(group) >= 3 else "medium",
                is_release=False,
                topic=topic,
            ))

    events.sort(key=lambda e: e.start_date or "", reverse=True)
    return events
