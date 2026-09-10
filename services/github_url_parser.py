"""GitHub URL 解析器：从各类 GitHub URL 提取结构化信息"""
import re
from dataclasses import dataclass, field
from typing import Optional
from urllib.parse import urlparse, parse_qs


@dataclass
class GitHubURLInfo:
    url: str
    owner: str = ""
    repo: str = ""
    url_type: str = "unknown"     # repository/commits/commit/release/pr/issue/docs/tree/other
    branch: str = ""
    sha: str = ""                 # commit SHA
    tag: str = ""                 # release tag
    pr_number: str = ""
    issue_number: str = ""
    file_path: str = ""           # blob/tree 后的路径
    since: str = ""               # commits?since=
    until: str = ""               # commits?until=
    raw_url: str = ""             # 对应 raw.githubusercontent.com URL（如适用）
    atom_feed_url: str = ""       # Atom feed URL（如适用）
    api_url: str = ""             # 对应 GitHub API URL


_GITHUB_HOSTS = {"github.com", "www.github.com"}


def parse_github_url(url: str) -> GitHubURLInfo:
    """解析 GitHub URL，返回结构化信息。"""
    info = GitHubURLInfo(url=url)
    try:
        parsed = urlparse(url)
    except Exception:
        return info

    host = parsed.netloc.lower().lstrip("www.")
    if host not in _GITHUB_HOSTS:
        return info

    path = parsed.path.strip("/")
    parts = [p for p in path.split("/") if p]
    qs = parse_qs(parsed.query)

    # since / until 参数（commits 列表使用）
    info.since = qs.get("since", [""])[0]
    info.until = qs.get("until", [""])[0]

    if len(parts) < 2:
        info.url_type = "other"
        return info

    info.owner = parts[0]
    info.repo = parts[1]

    # ── 派生 API 和 feed URL ────────────────────────────────
    _set_derived_urls(info, parts, parsed.query)

    if len(parts) == 2:
        info.url_type = "repository"
        info.api_url = f"https://api.github.com/repos/{info.owner}/{info.repo}"
        return info

    segment = parts[2].lower() if len(parts) > 2 else ""

    if segment == "commits":
        info.url_type = "commits"
        if len(parts) > 3:
            info.branch = parts[3]
        info.atom_feed_url = (
            f"https://github.com/{info.owner}/{info.repo}/commits/"
            f"{info.branch or 'main'}.atom"
            + (f"?since={info.since}&until={info.until}"
               if info.since or info.until else "")
        )
        info.api_url = (
            f"https://api.github.com/repos/{info.owner}/{info.repo}/commits"
            + _build_commits_query(info.branch, info.since, info.until)
        )

    elif segment == "commit":
        info.url_type = "commit"
        info.sha = parts[3] if len(parts) > 3 else ""
        info.api_url = (
            f"https://api.github.com/repos/{info.owner}/{info.repo}/commits/{info.sha}"
            if info.sha else
            f"https://api.github.com/repos/{info.owner}/{info.repo}/commits"
        )

    elif segment == "releases":
        info.url_type = "release"
        if len(parts) > 3 and parts[3].lower() == "tag":
            info.tag = parts[4] if len(parts) > 4 else ""
        info.atom_feed_url = f"https://github.com/{info.owner}/{info.repo}/releases.atom"
        info.api_url = (
            f"https://api.github.com/repos/{info.owner}/{info.repo}/releases/tags/{info.tag}"
            if info.tag else
            f"https://api.github.com/repos/{info.owner}/{info.repo}/releases/latest"
        )

    elif segment == "pull":
        info.url_type = "pr"
        info.pr_number = parts[3] if len(parts) > 3 else ""
        info.api_url = (
            f"https://api.github.com/repos/{info.owner}/{info.repo}/pulls/{info.pr_number}"
            if info.pr_number else
            f"https://api.github.com/repos/{info.owner}/{info.repo}/pulls"
        )

    elif segment == "issues":
        info.url_type = "issue"
        info.issue_number = parts[3] if len(parts) > 3 else ""
        info.api_url = (
            f"https://api.github.com/repos/{info.owner}/{info.repo}/issues/{info.issue_number}"
            if info.issue_number else
            f"https://api.github.com/repos/{info.owner}/{info.repo}/issues"
        )

    elif segment in ("blob", "tree"):
        # blob/main/README.md 或 tree/main/docs/
        file_parts = parts[4:] if len(parts) > 4 else []
        info.file_path = "/".join(file_parts)
        info.branch = parts[3] if len(parts) > 3 else "main"

        _doc_patterns = ["readme", "docs/", "documentation/", "examples/",
                         "skills/", "integrations/", "quickstart/",
                         "changelog", "release_notes"]
        fp_lower = info.file_path.lower()
        if any(pat in fp_lower for pat in _doc_patterns) or fp_lower.endswith(".md"):
            info.url_type = "docs"
        else:
            info.url_type = "tree"

        if segment == "blob" and info.file_path:
            info.raw_url = (
                f"https://raw.githubusercontent.com/{info.owner}/{info.repo}/"
                f"{info.branch}/{info.file_path}"
            )

    else:
        info.url_type = "other"

    return info


def _set_derived_urls(info: GitHubURLInfo, parts: list, query: str) -> None:
    """设置 README 等常见衍生 URL。"""
    if len(parts) >= 2:
        for branch in ("main", "master"):
            info.raw_url = info.raw_url or (
                f"https://raw.githubusercontent.com/{info.owner}/{info.repo}/{branch}/README.md"
            )
        break_val = None  # no-op placeholder


def _build_commits_query(branch: str, since: str, until: str) -> str:
    params = []
    if branch:
        params.append(f"sha={branch}")
    if since:
        params.append(f"since={since}")
    if until:
        params.append(f"until={until}")
    return ("?" + "&".join(params)) if params else ""
