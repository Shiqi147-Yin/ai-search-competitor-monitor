"""GitHub 专项信息抓取服务
优先级：Atom feed → raw README → 公开 API（匿名） → 普通网页 → 降级人工
不需要 Token 即可运行；匿名 API rate limit 时记录错误，不视为仓库不存在。
"""
import json
import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from typing import Optional

try:
    import requests
    _HAS_REQUESTS = True
except ImportError:
    _HAS_REQUESTS = False

from services.github_url_parser import parse_github_url, GitHubURLInfo
from services.github_analyzer import analyze_github_content

_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36"
)
_TIMEOUT = (10, 20)
_MAX_COMMITS = 10   # Atom feed 最多取几条 commit


@dataclass
class CommitInfo:
    sha: str = ""
    title: str = ""
    author: str = ""
    date: str = ""
    url: str = ""
    changed_files: list = field(default_factory=list)


@dataclass
class GitHubFetchResult:
    url: str
    url_info: Optional[GitHubURLInfo] = None
    status: str = "pending"           # success / partial / failed / restricted
    error: str = ""
    fetch_strategy: str = "github_special"
    # 通用字段
    title: str = ""
    description: str = ""
    published_date: str = ""
    content_snippet: str = ""
    # GitHub 专项字段
    repository_name: str = ""
    branch: str = ""
    commits: list = field(default_factory=list)   # list[CommitInfo]
    readme_content: str = ""
    change_analysis: dict = field(default_factory=dict)
    raw_api_status: int = 0


def fetch_github(url: str) -> GitHubFetchResult:
    """GitHub 专项入口，不向上抛异常。"""
    result = GitHubFetchResult(url=url)

    if not _HAS_REQUESTS:
        result.status = "failed"
        result.error = "requests 库未安装"
        return result

    try:
        info = parse_github_url(url)
        result.url_info = info
        result.repository_name = f"{info.owner}/{info.repo}" if info.owner and info.repo else ""
        result.branch = info.branch

        if not info.owner or not info.repo:
            result.status = "failed"
            result.error = "无法解析 owner/repo"
            return result

        if info.url_type == "commits":
            _fetch_commits(info, result)
        elif info.url_type == "commit":
            _fetch_single_commit(info, result)
        elif info.url_type == "release":
            _fetch_releases(info, result)
        elif info.url_type in ("docs", "tree"):
            _fetch_docs_or_tree(info, result)
        else:
            # repository / pr / issue / other → 先尝试 API，再尝试网页元信息
            _fetch_repo_meta(info, result)

        # 通用 GitHub 分析
        combined = f"{result.title} {result.description} {result.content_snippet}"
        result.change_analysis = analyze_github_content(
            url,
            title=result.title,
            description=result.description,
            content=result.content_snippet,
        )

    except Exception as e:
        result.status = "failed"
        result.error = f"{type(e).__name__}: {str(e)[:120]}"

    return result


# ── 内部实现 ──────────────────────────────────────────────────

def _get(url: str, accept: str = "application/json") -> tuple[int, str]:
    """发起 GET，返回 (status_code, text)。"""
    headers = {"User-Agent": _UA, "Accept": accept}
    try:
        resp = requests.get(url, headers=headers, timeout=_TIMEOUT, allow_redirects=True)
        return resp.status_code, resp.text
    except requests.exceptions.Timeout:
        return -1, "ConnectTimeout"
    except requests.exceptions.ConnectionError as e:
        return -2, f"ConnectionError: {str(e)[:80]}"
    except Exception as e:
        return -3, f"{type(e).__name__}: {str(e)[:80]}"


def _fetch_commits(info: GitHubURLInfo, result: GitHubFetchResult) -> None:
    """尝试 Atom feed → API → 降级。"""
    commits: list[CommitInfo] = []
    error_parts: list[str] = []

    # 1. Atom feed
    if info.atom_feed_url:
        code, text = _get(info.atom_feed_url, accept="application/atom+xml")
        if code == 200:
            commits = _parse_commits_atom(text)
            if commits:
                result.status = "success"
                result.title = f"{info.owner}/{info.repo} 最近提交（{len(commits)} 条）"
                result.commits = commits
                result.content_snippet = "; ".join(c.title for c in commits[:5])
                result.published_date = commits[0].date if commits else ""
                return
        else:
            error_parts.append(f"Atom feed HTTP {code}")

    # 2. GitHub API（匿名）
    if info.api_url:
        code, text = _get(info.api_url)
        result.raw_api_status = code
        if code == 200:
            try:
                data = json.loads(text)
                commits = _parse_api_commits(data, info.owner, info.repo)
                if commits:
                    result.status = "success"
                    result.title = f"{info.owner}/{info.repo} 最近提交（{len(commits)} 条）"
                    result.commits = commits
                    result.content_snippet = "; ".join(c.title for c in commits[:5])
                    result.published_date = commits[0].date if commits else ""
                    return
            except Exception as e:
                error_parts.append(f"API parse error: {e}")
        elif code == 403:
            error_parts.append("API HTTP 403 (rate limit or blocked, 非仓库不存在)")
            result.raw_api_status = 403
        elif code == 404:
            error_parts.append("API HTTP 404 (仓库不存在或私有)")
        else:
            error_parts.append(f"API HTTP {code}")

    result.status = "partial"
    result.error = "; ".join(error_parts) if error_parts else "未能获取提交列表"
    result.title = f"{info.owner}/{info.repo} commits ({info.branch or 'main'})"


def _parse_commits_atom(xml_text: str) -> list[CommitInfo]:
    """解析 GitHub commits Atom feed。"""
    commits = []
    try:
        ns = {"atom": "http://www.w3.org/2005/Atom"}
        root = ET.fromstring(xml_text)
        for entry in root.findall("atom:entry", ns)[:_MAX_COMMITS]:
            title_el = entry.find("atom:title", ns)
            author_el = entry.find("atom:author/atom:name", ns)
            updated_el = entry.find("atom:updated", ns)
            link_el = entry.find("atom:link", ns)
            sha = ""
            link_href = link_el.get("href", "") if link_el is not None else ""
            sha_match = re.search(r"/commit/([0-9a-f]{7,40})", link_href)
            if sha_match:
                sha = sha_match.group(1)[:7]
            commits.append(CommitInfo(
                sha=sha,
                title=(title_el.text or "").strip()[:120] if title_el is not None else "",
                author=(author_el.text or "").strip() if author_el is not None else "",
                date=(updated_el.text or "").strip()[:10] if updated_el is not None else "",
                url=link_href,
            ))
    except Exception:
        pass
    return commits


def _parse_api_commits(data, owner: str, repo: str) -> list[CommitInfo]:
    """解析 GitHub API commits 响应（list of commit objects）。"""
    commits = []
    if not isinstance(data, list):
        return commits
    for item in data[:_MAX_COMMITS]:
        sha = item.get("sha", "")[:7]
        msg = (item.get("commit", {}).get("message", "") or "").split("\n")[0][:120]
        author = item.get("commit", {}).get("author", {}).get("name", "")
        date = (item.get("commit", {}).get("author", {}).get("date", "") or "")[:10]
        link = f"https://github.com/{owner}/{repo}/commit/{item.get('sha','')}"
        commits.append(CommitInfo(sha=sha, title=msg, author=author, date=date, url=link))
    return commits


def _fetch_single_commit(info: GitHubURLInfo, result: GitHubFetchResult) -> None:
    """抓取单个 commit。"""
    if not info.sha:
        result.status = "partial"
        result.error = "无法解析 commit SHA"
        return

    code, text = _get(info.api_url)
    result.raw_api_status = code
    if code == 200:
        try:
            data = json.loads(text)
            msg = (data.get("commit", {}).get("message", "") or "").split("\n")[0][:120]
            author = data.get("commit", {}).get("author", {}).get("name", "")
            date = (data.get("commit", {}).get("author", {}).get("date", "") or "")[:10]
            files = [f.get("filename", "") for f in data.get("files", [])[:10]]
            result.title = msg
            result.published_date = date
            result.content_snippet = f"Author: {author}. Files: {', '.join(files[:5])}"
            result.commits = [CommitInfo(sha=info.sha, title=msg, author=author,
                                         date=date, url=info.url, changed_files=files)]
            result.status = "success"
        except Exception as e:
            result.status = "partial"
            result.error = f"API parse error: {e}"
    elif code == 403:
        result.status = "restricted"
        result.error = "API HTTP 403 (rate limit)"
    elif code == 404:
        result.status = "failed"
        result.error = "API HTTP 404"
    else:
        result.status = "partial"
        result.error = f"API HTTP {code}"


def _fetch_releases(info: GitHubURLInfo, result: GitHubFetchResult) -> None:
    """抓取 Release 信息：先 Atom，再 API。"""
    if info.atom_feed_url:
        code, text = _get(info.atom_feed_url, accept="application/atom+xml")
        if code == 200:
            try:
                ns = {"atom": "http://www.w3.org/2005/Atom"}
                root = ET.fromstring(text)
                entry = root.find("atom:entry", ns)
                if entry is not None:
                    title_el = entry.find("atom:title", ns)
                    updated_el = entry.find("atom:updated", ns)
                    link_el = entry.find("atom:link", ns)
                    result.title = (title_el.text or "").strip()[:120] if title_el is not None else ""
                    result.published_date = (updated_el.text or "")[:10] if updated_el is not None else ""
                    result.content_snippet = result.title
                    result.status = "success"
                    return
            except Exception:
                pass

    code, text = _get(info.api_url)
    result.raw_api_status = code
    if code == 200:
        try:
            data = json.loads(text)
            if isinstance(data, list):
                data = data[0] if data else {}
            result.title = data.get("name") or data.get("tag_name", "")
            result.published_date = (data.get("published_at") or "")[:10]
            result.content_snippet = (data.get("body") or "")[:500]
            result.status = "success"
        except Exception as e:
            result.status = "partial"
            result.error = f"API parse error: {e}"
    elif code == 403:
        result.status = "restricted"
        result.error = "API HTTP 403 (rate limit)"
    else:
        result.status = "partial"
        result.error = f"API HTTP {code}"


def _fetch_docs_or_tree(info: GitHubURLInfo, result: GitHubFetchResult) -> None:
    """抓取 blob/README/docs 文件：使用 raw URL。"""
    # 先尝试具体文件的 raw URL（已由 parse 生成）
    if info.raw_url and "raw.githubusercontent.com" in info.raw_url:
        code, text = _get(info.raw_url, accept="text/plain")
        if code == 200:
            result.readme_content = text[:3000]
            result.content_snippet = text[:500]
            label = info.file_path if info.file_path else "README.md"
            result.title = f"{info.owner}/{info.repo}: {label}"
            result.status = "success"
            return

    # 再尝试默认 README（main 或 master 分支）
    for branch in ("main", "master"):
        raw = f"https://raw.githubusercontent.com/{info.owner}/{info.repo}/{branch}/README.md"
        code, text = _get(raw, accept="text/plain")
        if code == 200:
            result.readme_content = text[:3000]
            result.content_snippet = text[:500]
            result.title = f"{info.owner}/{info.repo} README"
            result.status = "success"
            return

    result.status = "partial"
    result.error = "无法获取文档内容"


def _fetch_repo_meta(info: GitHubURLInfo, result: GitHubFetchResult) -> None:
    """抓取仓库元信息（API）。"""
    api = f"https://api.github.com/repos/{info.owner}/{info.repo}"
    code, text = _get(api)
    result.raw_api_status = code
    if code == 200:
        try:
            data = json.loads(text)
            result.title = data.get("full_name", "") + (f": {data.get('description','')}" if data.get("description") else "")
            result.description = data.get("description", "")
            result.published_date = (data.get("updated_at") or "")[:10]
            result.content_snippet = result.description
            result.status = "success"
        except Exception as e:
            result.status = "partial"
            result.error = f"API parse error: {e}"
    elif code == 403:
        result.status = "restricted"
        result.error = "API HTTP 403 (rate limit, 非仓库不存在)"
    elif code == 404:
        result.status = "failed"
        result.error = "仓库不存在或为私有仓库"
    else:
        result.status = "partial"
        result.error = f"API HTTP {code}"
