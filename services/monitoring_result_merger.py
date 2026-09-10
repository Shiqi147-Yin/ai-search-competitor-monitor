"""官方结果与 Querit 补充结果合并器
官方主动巡检结果优先，Querit 只作为补充发现层。
"""
import re
from dataclasses import dataclass, field

from services.official_update_normalizer import OfficialUpdateItem


@dataclass
class MergeResult:
    official_items: list = field(default_factory=list)     # 官方主动发现（含已合并 both）
    querit_supplement: list = field(default_factory=list)  # Querit 独有补充线索
    merged_count: int = 0                                   # 合并条数（避免重复）


def _normalize_url(url: str) -> str:
    """去除尾部斜杠和查询参数，用于去重比较。"""
    url = url.strip().rstrip("/")
    if "?" in url:
        url = url[:url.index("?")]
    return url.lower()


def _title_word_overlap(title_a: str, title_b: str) -> float:
    """计算两个标题的词集合 Jaccard 相似度（忽略大小写）。"""
    stop = {"a", "an", "the", "and", "or", "in", "on", "for", "of", "to", "is", "are", "with"}
    words_a = {w.lower() for w in re.findall(r"[a-zA-Z\u4e00-\u9fff]{2,}", title_a) if w.lower() not in stop}
    words_b = {w.lower() for w in re.findall(r"[a-zA-Z\u4e00-\u9fff]{2,}", title_b) if w.lower() not in stop}
    if not words_a or not words_b:
        return 0.0
    return len(words_a & words_b) / len(words_a | words_b)


def merge_results(
    official_items: list[OfficialUpdateItem],
    querit_items: list[OfficialUpdateItem],
    title_threshold: float = 0.5,
) -> MergeResult:
    """合并官方巡检结果与 Querit 补充结果。

    规则：
    1. 官方结果完整保留，URL / 日期 / 来源不被 Querit 覆盖
    2. Querit 条目 URL 与官方一致 → 合并（discovery_method = "both"），不重复
    3. Querit 条目标题词重叠 ≥ title_threshold → 视为同一事件，合并
    4. 无法匹配的 Querit 条目进入 querit_supplement 列表

    Returns:
        MergeResult
    """
    result = MergeResult()
    official_copy: list[OfficialUpdateItem] = list(official_items)
    merged_count = 0

    official_urls = {_normalize_url(item.source_url): idx for idx, item in enumerate(official_copy) if item.source_url}

    for q_item in querit_items:
        q_url = _normalize_url(q_item.source_url)
        matched_idx = None

        # 1. URL 精确匹配
        if q_url and q_url in official_urls:
            matched_idx = official_urls[q_url]

        # 2. 标题相似度匹配
        if matched_idx is None:
            for idx, o_item in enumerate(official_copy):
                if _title_word_overlap(q_item.update_title, o_item.update_title) >= title_threshold:
                    matched_idx = idx
                    break

        if matched_idx is not None:
            # 合并：标记 discovery_method = "both"，官方字段不被覆盖
            official_copy[matched_idx].discovery_method = "both"
            # 补充 Querit 的 querit_relevance（如果官方没有）
            if not official_copy[matched_idx].querit_relevance and q_item.querit_relevance:
                official_copy[matched_idx].querit_relevance = q_item.querit_relevance
            merged_count += 1
        else:
            # Querit 独有新线索
            q_item.discovery_method = "querit_supplement"
            result.querit_supplement.append(q_item)

    result.official_items = official_copy
    result.merged_count = merged_count
    return result
