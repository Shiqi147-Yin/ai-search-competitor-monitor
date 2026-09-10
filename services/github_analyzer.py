"""GitHub URL 专项分析（路径规则 + 关键词扫描，不调用 GitHub API）"""
import re
from urllib.parse import urlparse

# ── 关键词表 ──────────────────────────────────────────────────
_CAPABILITY_KEYWORDS = [
    "new api", "search mode", "streaming", "research", "deep search",
    "mcp", "oauth", "authentication", "sdk", "timeout", "performance",
    "reliability", "pricing", "quota", "agent skills", "rate limit",
    "new endpoint", "new feature",
]

_INTEGRATION_KEYWORDS = [
    "integration", "connector", "plugin", "skill", "mcp server",
    "coding agent", "ai ide", "langchain", "llamaindex", "crewai",
    "mastra", "n8n", "flowise", "dify", "kiro", "nvidia", "cerebras",
    "openai", "anthropic", "gemini", "cursor", "copilot",
]

_DX_KEYWORDS = [
    "readme", "quickstart", "installation", "example", "tutorial",
    "migration guide", "faq", "troubleshooting", "documentation",
    "getting started", "how to", "cookbook", "guide",
]

# ── URL 类型识别 ──────────────────────────────────────────────
def detect_github_event_type(url: str) -> str:
    """根据 URL 路径识别 GitHub 事件类型。"""
    path = urlparse(url).path.lower()
    parts = [p for p in path.split("/") if p]

    if "/commit/" in path:
        return "commit"
    if "/releases/tag/" in path or "/releases" in path:
        return "release"
    if "/pull/" in path:
        return "pr"
    if "/issues/" in path:
        return "issue"
    if "/blob/" in path or "/tree/" in path:
        # 看路径里是否含文档类文件
        doc_patterns = ["readme", "docs/", "documentation", "changelog", "quickstart"]
        if any(p in path for p in doc_patterns):
            return "docs"
        return "tree"
    # 仓库根：恰好两段路径（owner/repo）
    if len(parts) == 2:
        return "repository"
    return "other"


def extract_repo_name(url: str) -> str:
    """提取 owner/repo 格式的仓库名。"""
    path = urlparse(url).path
    parts = [p for p in path.split("/") if p]
    if len(parts) >= 2:
        return f"{parts[0]}/{parts[1]}"
    return ""


def _scan_keywords(text: str, keywords: list[str]) -> list[str]:
    """返回在 text 中出现过的关键词列表（不区分大小写）。"""
    text_lower = text.lower()
    return [kw for kw in keywords if kw in text_lower]


def analyze_github_content(
    url: str,
    title: str = "",
    description: str = "",
    content: str = "",
) -> dict:
    """分析 GitHub 页面内容，返回结构化标记字段。"""
    combined = f"{title} {description} {content}".lower()
    event_type = detect_github_event_type(url)
    repo_name = extract_repo_name(url)

    cap_hits = _scan_keywords(combined, _CAPABILITY_KEYWORDS)
    int_hits = _scan_keywords(combined, _INTEGRATION_KEYWORDS)
    dx_hits = _scan_keywords(combined, _DX_KEYWORDS)

    docs_changed = int(event_type == "docs" or bool(dx_hits))
    capability_change = int(bool(cap_hits))
    integration_change = int(bool(int_hits))
    developer_experience_change = int(bool(dx_hits))

    change_summary = build_change_summary(
        event_type, repo_name, title, cap_hits, int_hits, dx_hits
    )

    return {
        "github_event_type": event_type,
        "repository_name": repo_name,
        "docs_changed": docs_changed,
        "capability_change": capability_change,
        "integration_change": integration_change,
        "developer_experience_change": developer_experience_change,
        "change_summary": change_summary,
    }


def build_change_summary(
    event_type: str,
    repo: str,
    title: str,
    cap_hits: list[str],
    int_hits: list[str],
    dx_hits: list[str],
) -> str:
    """生成变化摘要描述，确保非空。"""
    parts: list[str] = []

    type_label = {
        "commit": "提交更新",
        "release": "发布新版本",
        "pr": "Pull Request",
        "issue": "Issue",
        "docs": "文档更新",
        "repository": "仓库",
        "tree": "文件变更",
    }.get(event_type, "更新")

    repo_str = f"[{repo}] " if repo else ""
    parts.append(f"{repo_str}GitHub {type_label}")

    if title:
        parts.append(f"：{title[:80]}")

    flags: list[str] = []
    if cap_hits:
        flags.append(f"产品能力（{', '.join(cap_hits[:2])}）")
    if int_hits:
        flags.append(f"生态集成（{', '.join(int_hits[:2])}）")
    if dx_hits:
        flags.append(f"开发者体验（{', '.join(dx_hits[:2])}）")

    if flags:
        parts.append("  |  涉及：" + "、".join(flags))

    return "".join(parts)
