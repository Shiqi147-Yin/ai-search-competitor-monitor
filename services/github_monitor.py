"""GitHub 官方仓库主动巡检服务
不依赖 Querit API，主动通过 Atom feed / GitHub API 获取指定仓库的 commits 和 releases。
复用 github_fetcher 的底层网络请求，但自行按时间窗口过滤，支持逐仓库独立失败。
"""
import json
import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from datetime import datetime, timezone

try:
    import requests as _req
    _HAS_REQUESTS = True
except ImportError:
    _HAS_REQUESTS = False

_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)
_TIMEOUT = (10, 20)
_MAX_COMMITS = 30  # 每次最多取多少条，再按窗口过滤


@dataclass
class GitHubCommitRecord:
    repository: str = ""       # "tavily-ai/tavily-mcp"
    commit_sha: str = ""
    commit_title: str = ""
    commit_url: str = ""
    commit_date: str = ""      # YYYY-MM-DD
    author: str = ""
    changed_files: list = field(default_factory=list)
    additions: int = 0
    deletions: int = 0
    change_summary: str = ""


@dataclass
class GitHubReleaseRecord:
    repository: str = ""
    version: str = ""
    release_title: str = ""
    release_url: str = ""
    published_at: str = ""     # YYYY-MM-DD
    release_notes: str = ""


# ── 内部工具 ──────────────────────────────────────────────────────

def _get(url: str, accept: str = "application/json") -> tuple[int, str]:
    if not _HAS_REQUESTS:
        return -1, "requests not installed"
    try:
        r = _req.get(url, headers={"User-Agent": _UA, "Accept": accept},
                     timeout=_TIMEOUT, allow_redirects=True)
        return r.status_code, r.text
    except Exception as e:
        return -1, str(e)[:120]


def _within_window(date_str: str, window_start: str, window_end: str) -> bool:
    """判断 date_str（YYYY-MM-DD 或 ISO 8601）是否在 [window_start, window_end] 内。"""
    if not date_str:
        return False

    def _parse(s: str):
        s = s.strip()
        for fmt in (
            "%Y-%m-%dT%H:%M:%SZ",
            "%Y-%m-%dT%H:%M:%S.%fZ",
            "%Y-%m-%dT%H:%M:%S%z",
            "%Y-%m-%d %H:%M:%S",
            "%Y-%m-%d",
        ):
            try:
                d = datetime.strptime(s, fmt)
                if d.tzinfo is None:
                    d = d.replace(tzinfo=timezone.utc)
                return d
            except Exception:
                continue
        # last resort: fromisoformat
        try:
            d = datetime.fromisoformat(s.replace("Z", "+00:00"))
            if d.tzinfo is None:
                d = d.replace(tzinfo=timezone.utc)
            return d
        except Exception:
            return None

    try:
        dt = _parse(date_str)
        ws = _parse(window_start)
        we = _parse(window_end)
        if dt is None or ws is None or we is None:
            return False
        return ws <= dt <= we
    except Exception:
        return False


# ── 核心抓取函数 ──────────────────────────────────────────────────

def monitor_repo_commits(
    owner: str,
    repo: str,
    window_start: str,
    window_end: str,
) -> list[GitHubCommitRecord]:
    """获取仓库时间窗口内的 commits。
    策略：Atom feed → GitHub API（匿名）→ 空列表（不抛异常）
    仓库首页本身不作为 commit，不返回。
    """
    repo_full = f"{owner}/{repo}"
    commits: list[GitHubCommitRecord] = []

    # 1. Atom feed（无需 token，公开仓库均可访问）
    for branch in ("main", "master"):
        atom_url = f"https://github.com/{owner}/{repo}/commits/{branch}.atom"
        code, text = _get(atom_url, accept="application/atom+xml")
        if code != 200:
            continue
        try:
            ns = {"atom": "http://www.w3.org/2005/Atom"}
            root = ET.fromstring(text)
            for entry in root.findall("atom:entry", ns)[:_MAX_COMMITS]:
                title_el = entry.find("atom:title", ns)
                author_el = entry.find("atom:author/atom:name", ns)
                updated_el = entry.find("atom:updated", ns)
                link_el = entry.find("atom:link", ns)
                link_href = link_el.get("href", "") if link_el is not None else ""
                sha_match = re.search(r"/commit/([0-9a-f]{7,40})", link_href)
                sha = sha_match.group(1)[:7] if sha_match else ""
                commit_date = (updated_el.text or "")[:10] if updated_el is not None else ""
                if not _within_window(commit_date, window_start, window_end):
                    continue
                title_text = (title_el.text or "").strip()[:120] if title_el is not None else ""
                commits.append(GitHubCommitRecord(
                    repository=repo_full,
                    commit_sha=sha,
                    commit_title=title_text,
                    commit_url=link_href,
                    commit_date=commit_date,
                    author=(author_el.text or "").strip() if author_el is not None else "",
                ))
        except Exception:
            pass
        if commits:
            return commits  # Atom 成功就不再尝试 API

    # 2. GitHub API（匿名，60 req/hour；rate limit 时返回空，不中断）
    api_url = f"https://api.github.com/repos/{owner}/{repo}/commits?per_page={_MAX_COMMITS}"
    code, text = _get(api_url)
    if code == 200:
        try:
            data = json.loads(text)
            if isinstance(data, list):
                for item in data:
                    sha = (item.get("sha", "") or "")[:7]
                    msg = (item.get("commit", {}).get("message", "") or "").split("\n")[0][:120]
                    author = item.get("commit", {}).get("author", {}).get("name", "") or ""
                    date = (item.get("commit", {}).get("author", {}).get("date", "") or "")[:10]
                    link = f"https://github.com/{owner}/{repo}/commit/{item.get('sha', '')}"
                    if not _within_window(date, window_start, window_end):
                        continue
                    commits.append(GitHubCommitRecord(
                        repository=repo_full,
                        commit_sha=sha,
                        commit_title=msg,
                        commit_url=link,
                        commit_date=date,
                        author=author,
                    ))
        except Exception:
            pass

    return commits


def monitor_repo_releases(
    owner: str,
    repo: str,
    window_start: str,
    window_end: str,
) -> list[GitHubReleaseRecord]:
    """获取仓库时间窗口内的 releases。
    策略：Atom feed → GitHub API
    """
    repo_full = f"{owner}/{repo}"
    releases: list[GitHubReleaseRecord] = []

    # 1. Atom feed
    atom_url = f"https://github.com/{owner}/{repo}/releases.atom"
    code, text = _get(atom_url, accept="application/atom+xml")
    if code == 200:
        try:
            ns = {"atom": "http://www.w3.org/2005/Atom"}
            root = ET.fromstring(text)
            for entry in root.findall("atom:entry", ns)[:20]:
                title_el = entry.find("atom:title", ns)
                updated_el = entry.find("atom:updated", ns)
                link_el = entry.find("atom:link", ns)
                pub_date = (updated_el.text or "")[:10] if updated_el is not None else ""
                if not _within_window(pub_date, window_start, window_end):
                    continue
                link_href = link_el.get("href", "") if link_el is not None else ""
                version = link_href.split("/tag/")[-1] if "/tag/" in link_href else ""
                releases.append(GitHubReleaseRecord(
                    repository=repo_full,
                    version=version,
                    release_title=(title_el.text or "").strip()[:120] if title_el is not None else "",
                    release_url=link_href,
                    published_at=pub_date,
                ))
        except Exception:
            pass

    if releases:
        return releases

    # 2. GitHub API
    api_url = f"https://api.github.com/repos/{owner}/{repo}/releases?per_page=20"
    code, text = _get(api_url)
    if code == 200:
        try:
            data = json.loads(text)
            if isinstance(data, list):
                for item in data:
                    pub = (item.get("published_at") or "")[:10]
                    if not _within_window(pub, window_start, window_end):
                        continue
                    releases.append(GitHubReleaseRecord(
                        repository=repo_full,
                        version=item.get("tag_name", ""),
                        release_title=(item.get("name", "") or "")[:120],
                        release_url=item.get("html_url", ""),
                        published_at=pub,
                        release_notes=(item.get("body") or "")[:1000],
                    ))
        except Exception:
            pass

    return releases


def run_github_monitor(
    competitor: str,
    github_config: dict,
    window_start: str,
    window_end: str,
) -> dict:
    """遍历配置仓库执行巡检。单仓库失败不影响其他仓库。

    Args:
        competitor:     竞品名称（当前仅用于日志）
        github_config:  official_monitoring_sources.yaml 中的 github 段
                        {"owner": str, "repositories": [{"name": str, "monitor": [...]}]}
        window_start:   ISO 8601
        window_end:     ISO 8601

    Returns:
        {
            "commits":  list[GitHubCommitRecord],
            "releases": list[GitHubReleaseRecord],
            "errors":   list[dict],
        }
    """
    owner = github_config.get("owner", "")
    repos = github_config.get("repositories", [])
    result: dict = {"commits": [], "releases": [], "errors": []}

    for repo_cfg in repos:
        if isinstance(repo_cfg, dict):
            repo_name = repo_cfg.get("name", "")
            monitor_types = repo_cfg.get("monitor", ["commits", "releases"])
        else:
            repo_name = str(repo_cfg)
            monitor_types = ["commits", "releases"]

        if not repo_name:
            continue

        if "commits" in monitor_types:
            try:
                commits = monitor_repo_commits(owner, repo_name, window_start, window_end)
                result["commits"].extend(commits)
            except Exception as e:
                result["errors"].append({
                    "repository": f"{owner}/{repo_name}",
                    "source_type": "commits",
                    "error": f"{type(e).__name__}: {str(e)[:120]}",
                })

        if "releases" in monitor_types:
            try:
                releases = monitor_repo_releases(owner, repo_name, window_start, window_end)
                result["releases"].extend(releases)
            except Exception as e:
                result["errors"].append({
                    "repository": f"{owner}/{repo_name}",
                    "source_type": "releases",
                    "error": f"{type(e).__name__}: {str(e)[:120]}",
                })

    return result
