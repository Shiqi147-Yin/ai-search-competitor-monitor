"""GitHub 事件业务相关性评分器
为 GitHubAggregatedEvent 评估与竞品情报（Search API / 产品能力）的相关性。
配置驱动，不在公共代码中硬编码竞品名。
"""
import re
from dataclasses import dataclass

# ── 相关性分类 ─────────────────────────────────────────────────
RELEVANCE_CATEGORIES = [
    "core_search_api",      # 搜索/检索核心能力变化
    "product_capability",   # 产品功能新增或变更
    "sdk_api_change",       # SDK / API 参数、接口、schema 变化
    "integration_ecosystem",# 第三方集成、connector、MCP
    "developer_experience", # DX 改进：文档、CLI、错误提示等
    "maintenance",          # 版本 bump、lint、依赖升级
    "internal_only",        # 内部实现，不影响公开能力
    "unrelated",            # 完全无关
]

# 默认主结果白名单
PRIMARY_RESULT_CATEGORIES = {
    "core_search_api",
    "product_capability",
    "sdk_api_change",
    "integration_ecosystem",
    "developer_experience",
}

# 默认只进诊断区的类别
DIAGNOSTIC_ONLY_CATEGORIES = {
    "maintenance",
    "internal_only",
    "unrelated",
}

# ── 内置关键词（可被配置覆盖）────────────────────────────────────
_DEFAULT_KEYWORDS = {
    "core": ["search", "retrieval", "contents", "content", "crawl", "deep", "research",
             "websets", "highlights", "neural", "semantic", "embedding"],
    "api_sdk": ["api", "sdk", "parameter", "deprecated", "endpoint", "response", "schema",
                "typed", "interface", "payload", "field", "argument"],
    "integrations": ["mcp", "agent", "integration", "connector", "langchain", "llamaindex",
                     "n8n", "vercel", "plugin", "openai", "anthropic", "framework"],
    "low_value": ["typo", "lint", "formatting", "prettier", "ci", "cd",
                  "bump", "pin", "reformat", "whitespace", "workflow"],
}

# Release/version bump 标题模式
_RELEASE_PATTERNS = re.compile(
    r"(chore[:\(].*release|release\s+v?\d+\.\d+|bump\s+version|version\s+bump|"
    r"chore\(master\).*release|prepare\s+release|cut\s+release)",
    re.IGNORECASE,
)


@dataclass
class RelevanceResult:
    category: str = "unrelated"
    score: float = 0.0           # 0.0 ~ 1.0
    reason: str = ""
    is_release_or_version_bump: bool = False
    should_be_primary_result: bool = False


def _load_keywords(config_keywords: dict = None) -> dict:
    """合并配置关键词与内置默认关键词。"""
    merged = {k: list(v) for k, v in _DEFAULT_KEYWORDS.items()}
    if config_keywords:
        for cat, words in config_keywords.items():
            merged.setdefault(cat, [])
            merged[cat].extend(words)
    return merged


def _is_release_bump(title: str) -> bool:
    return bool(_RELEASE_PATTERNS.search(title))


def classify_github_event_relevance(
    event_title: str,
    key_changes: list[str],
    changed_files: list[str],
    repository: str = "",
    config_keywords: dict = None,
) -> RelevanceResult:
    """为单个 GitHubAggregatedEvent 评估业务相关性。

    Args:
        event_title:    聚合事件标题
        key_changes:    原始 commit 标题列表
        changed_files:  变更文件路径列表
        repository:     仓库全名（如 "exa-labs/exa-py"）
        config_keywords: 来自 official_monitoring_sources.yaml 的关键词配置

    Returns:
        RelevanceResult
    """
    kw = _load_keywords(config_keywords)
    all_titles = [event_title] + (key_changes or [])
    combined = " ".join(all_titles).lower()
    files_combined = " ".join(changed_files or []).lower()

    result = RelevanceResult()

    # ── 1. 是否 release / version bump ──────────────────────
    valid_titles = [t for t in all_titles if t]
    release_count = sum(1 for t in valid_titles if _is_release_bump(t))
    if valid_titles and release_count >= max(1, len(valid_titles) // 2):
        # SDK releases are product_capability, not just maintenance
        ver_match = None
        for t in valid_titles:
            ver_match = re.search(r"(v?\d+\.\d+[\.\d]*)", t)
            if ver_match:
                break
        result.is_release_or_version_bump = True
        if ver_match:
            result.category = "product_capability"
            result.score = 0.6
            result.reason = f"SDK Release {ver_match.group(1)}: {release_count}/{len(valid_titles)} commits match"
            result.should_be_primary_result = True
        else:
            result.category = "maintenance"
            result.score = 0.3
            result.reason = f"Version-bump without version: {release_count}/{len(valid_titles)} commits"
            result.should_be_primary_result = False
        return result

    # ── 2. 低价值词 → maintenance ────────────────────────────
    low_value_hits = [w for w in kw.get("low_value", []) if w in combined]
    if len(low_value_hits) >= 2 and not any(w in combined for w in kw.get("core", [])):
        result.category = "maintenance"
        result.score = 0.2
        result.reason = f"Low-value keywords: {low_value_hits[:3]}"
        result.should_be_primary_result = False
        return result

    # ── 3. API / SDK 显式 deprecation / breaking change（优先于 core 关键词）─
    sdk_hits = [w for w in kw.get("api_sdk", []) if w in combined]
    if sdk_hits and any(w in combined for w in ("deprecated", "deprecate", "breaking", "removed", "drop")):
        result.category = "sdk_api_change"
        result.score = 0.9
        result.reason = f"SDK/API deprecation or breaking change: {sdk_hits[:3]}"
        result.should_be_primary_result = True
        return result

    # ── 4. 核心搜索能力 ──────────────────────────────────────
    core_hits = [w for w in kw.get("core", []) if w in combined]
    if core_hits:
        result.category = "core_search_api"
        result.score = min(0.5 + len(core_hits) * 0.1, 1.0)
        result.reason = f"Core search keywords: {core_hits[:3]}"
        result.should_be_primary_result = True
        return result

    # ── 5. API / SDK 其他变化 ────────────────────────────────
    if sdk_hits:
        result.category = "sdk_api_change"
        result.score = min(0.4 + len(sdk_hits) * 0.1, 0.85)
        result.reason = f"SDK/API keywords: {sdk_hits[:3]}"
        result.should_be_primary_result = True
        return result

    # ── 5. 集成生态 ──────────────────────────────────────────
    int_hits = [w for w in kw.get("integrations", []) if w in combined]
    if int_hits:
        # 判断是否影响公开能力：文件路径 OR commit 描述中含公开能力词
        public_signal_files = ("src/", "lib/", "index.", "tool", "plugin", "connector")
        public_signal_words = ("streaming", "resumable", "heartbeat", "agent_run",
                               "capability", "new tool", "new feature", "package metadata")
        is_public = (
            any(seg in files_combined for seg in public_signal_files) or
            any(seg in combined for seg in public_signal_words)
        )
        result.category = "integration_ecosystem" if is_public else "internal_only"
        result.score = 0.7 if is_public else 0.25
        result.reason = f"Integration keywords: {int_hits[:3]} public={is_public}"
        result.should_be_primary_result = is_public
        return result

    # ── 6. DX / 文档 ─────────────────────────────────────────
    if any(w in combined for w in ("readme", "documentation", "example", "getting started", "tutorial")):
        result.category = "developer_experience"
        result.score = 0.5
        result.reason = "Developer documentation update"
        result.should_be_primary_result = True
        return result

    # ── 7. 默认：无法判断 ────────────────────────────────────
    result.category = "unrelated"
    result.score = 0.1
    result.reason = "No matching keywords found"
    result.should_be_primary_result = False
    return result


def filter_events_by_relevance(
    events: list,
    config_keywords: dict = None,
    min_score: float = 0.0,
) -> tuple[list, list]:
    """为事件列表评分并分为主结果和诊断区。

    Returns:
        (primary_events, diagnostic_events)
    """
    primary = []
    diagnostic = []

    for event in events:
        rel = classify_github_event_relevance(
            event_title=event.event_title,
            key_changes=getattr(event, "key_changes", []),
            changed_files=getattr(event, "changed_files", []),
            repository=getattr(event, "repository", ""),
            config_keywords=config_keywords,
        )
        # 附加相关性字段到 event（动态添加属性）
        event.github_relevance = rel.category
        event.github_relevance_score = rel.score
        event.github_relevance_reason = rel.reason
        event.is_release_or_version_bump = rel.is_release_or_version_bump

        if rel.should_be_primary_result and rel.score >= min_score:
            primary.append(event)
        else:
            diagnostic.append(event)

    return primary, diagnostic
