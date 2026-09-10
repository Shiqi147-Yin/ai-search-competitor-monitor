"""统一官网与 GitHub 结果归一化器
将 Blog / Docs / GitHub commit 聚合事件 / GitHub release
统一转换为 OfficialUpdateItem，便于后续展示和合并。
"""
from dataclasses import dataclass, field

from services.website_monitor import WebsiteUpdateItem
from services.github_monitor import GitHubReleaseRecord
from services.github_event_aggregator import GitHubAggregatedEvent


@dataclass
class OfficialUpdateItem:
    competitor: str = ""
    update_title: str = ""
    update_date: str = ""            # 展示用日期（来自 published_at 或 updated_at 或 commit_date）
    source_channel: str = ""         # website_blog / website_docs / website_integration / github_commit_group / github_release
    content_type: str = ""           # article / docs_update / commit_group / release
    source_url: str = ""
    official_source: bool = True
    published_at: str = ""           # Blog 文章发布时间（仅 Blog 使用）
    updated_at: str = ""             # Docs 更新时间（来自 sitemap lastmod，仅 Docs 使用）
    first_seen_at: str = ""
    last_seen_at: str = ""
    update_status: str = ""          # new_page / substantive_update / first_seen / metadata_only / unchanged
    summary: str = ""
    key_points: list = field(default_factory=list)
    category: str = ""
    importance: str = "medium"
    querit_relevance: str = ""
    discovery_method: str = "official_direct"
    import_eligible: bool = True
    evidence_urls: list = field(default_factory=list)
    docs_page_role: str = ""
    is_generic_page: bool = False
    is_entry_page: bool = False
    within_window: bool = False
    # Querit supplement 专属字段
    matched_competitor: str = ""      # Querit 识别的竞品
    is_official_domain: bool = False  # 是否属于官方域名
    duplicate_of_official: str = ""   # 重复时指向官方结果 URL
    supplement_relevance: str = ""    # high / medium / low


def normalize_blog_item(item: WebsiteUpdateItem, competitor: str = "") -> OfficialUpdateItem:
    """Blog 文章 → OfficialUpdateItem。published_at 赋值，updated_at 不碰。"""
    return OfficialUpdateItem(
        competitor=competitor or item.competitor,
        update_title=item.title,
        update_date=item.published_at,          # Blog 用发布时间作为展示日期
        source_channel="website_blog",
        content_type="article",
        source_url=item.source_url,
        published_at=item.published_at,
        updated_at="",                          # Blog 不填 updated_at
        update_status=item.update_status,
        summary=item.summary,
        docs_page_role="detail_article",
        is_generic_page=False,
        is_entry_page=item.is_entry_page,
        discovery_method=item.discovery_method,
        import_eligible=item.import_eligible,
        within_window=item.within_window,
        evidence_urls=[item.source_url] if item.source_url else [],
    )


def normalize_docs_item(item: WebsiteUpdateItem, competitor: str = "") -> OfficialUpdateItem:
    """Docs / Integration 页面 → OfficialUpdateItem。updated_at 赋值，published_at 严格不写。"""
    channel = "website_integration" if item.source_type == "integration" else "website_docs"
    return OfficialUpdateItem(
        competitor=competitor or item.competitor,
        update_title=item.title,
        update_date=item.updated_at,            # Docs 用 lastmod 作为展示日期
        source_channel=channel,
        content_type="docs_update",
        source_url=item.source_url,
        published_at="",                        # Docs 严格不写 published_at
        updated_at=item.updated_at,
        update_status=item.update_status,
        summary=item.summary,
        docs_page_role=item.page_role,
        is_generic_page=item.is_generic_page,
        is_entry_page=item.is_entry_page,
        discovery_method=item.discovery_method,
        import_eligible=item.import_eligible,
        within_window=item.within_window,
        evidence_urls=[item.source_url] if item.source_url else [],
    )


def normalize_github_event(event: GitHubAggregatedEvent, competitor: str = "") -> OfficialUpdateItem:
    """GitHub commit 聚合事件 → OfficialUpdateItem。使用 start_date 作为展示日期。"""
    return OfficialUpdateItem(
        competitor=competitor,
        update_title=event.event_title,
        update_date=event.start_date,           # commit 日期（不是发布时间）
        source_channel="github_commit_group",
        content_type="commit_group",
        source_url=event.commit_urls[0] if event.commit_urls else "",
        published_at="",
        updated_at="",
        update_status="new_page",               # GitHub commit 总是"新发现"
        summary=event.summary,
        key_points=event.key_changes,
        category=event.category,
        importance=event.importance,
        discovery_method="official_direct",
        import_eligible=True,
        evidence_urls=event.commit_urls,
        within_window=True,                     # 已经过时间窗口过滤
    )


def normalize_github_release(release: GitHubReleaseRecord, competitor: str = "") -> OfficialUpdateItem:
    """GitHub release → OfficialUpdateItem。"""
    return OfficialUpdateItem(
        competitor=competitor,
        update_title=release.release_title or f"{release.repository} {release.version}",
        update_date=release.published_at,
        source_channel="github_release",
        content_type="release",
        source_url=release.release_url,
        published_at=release.published_at,
        updated_at="",
        update_status="new_page",
        summary=release.release_notes[:300] if release.release_notes else "",
        key_points=[release.release_notes[:200]] if release.release_notes else [],
        category="feature",
        importance="high",
        discovery_method="official_direct",
        import_eligible=True,
        evidence_urls=[release.release_url] if release.release_url else [],
        within_window=True,
    )


def normalize_all(
    competitor: str,
    blog_items: list = None,
    docs_items: list = None,
    integration_items: list = None,
    github_events: list = None,
    github_releases: list = None,
) -> list[OfficialUpdateItem]:
    """批量归一化所有来源，返回统一列表。"""
    result: list[OfficialUpdateItem] = []

    for item in (blog_items or []):
        result.append(normalize_blog_item(item, competitor))

    for item in (docs_items or []):
        result.append(normalize_docs_item(item, competitor))

    for item in (integration_items or []):
        result.append(normalize_docs_item(item, competitor))

    for event in (github_events or []):
        result.append(normalize_github_event(event, competitor))

    for release in (github_releases or []):
        result.append(normalize_github_release(release, competitor))

    return result
