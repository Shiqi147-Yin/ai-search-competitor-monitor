"""新鲜度过滤服务
根据时间窗口判断每条结果的新鲜度状态。
"""
from dataclasses import dataclass
from datetime import datetime, timezone, timedelta
from typing import Optional

from services.publish_date_parser import ParsedDate, parse_published_date


@dataclass
class FreshnessResult:
    freshness_status: str = "date_missing"
    # within_window | outside_window | future_date | date_missing | date_invalid
    days_from_search: Optional[int] = None
    window_start: str = ""
    window_end: str = ""
    freshness_reason: str = ""
    normalized_published_at: str = ""
    raw_published_date: str = ""
    date_status: str = "missing"
    date_source: str = "none"
    date_confidence: float = 0.0
    date_conflict: bool = False
    should_default_select: bool = False


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def compute_window(time_window_days: int, reference_time: Optional[datetime] = None) -> tuple[datetime, datetime]:
    """计算时间窗口 (window_start, window_end)。包含边界：pub_dt >= window_start。"""
    end = reference_time or _now_utc()
    # 边界包含：start 设为整天开始
    start = end - timedelta(days=time_window_days)
    return start, end


def check_freshness(
    record: dict,
    time_window_days: int,
    reference_time: Optional[datetime] = None,
) -> FreshnessResult:
    """判断单条记录的新鲜度状态。"""
    window_start, window_end = compute_window(time_window_days, reference_time)

    parsed = parse_published_date(
        record,
        url=record.get("source_url", ""),
        title=record.get("title", ""),
    )

    result = FreshnessResult(
        window_start=window_start.strftime("%Y-%m-%dT%H:%M:%SZ"),
        window_end=window_end.strftime("%Y-%m-%dT%H:%M:%SZ"),
        raw_published_date=parsed.raw_date,
        date_status=parsed.date_status,
        date_source=parsed.date_source,
        date_confidence=parsed.date_confidence,
    )

    if parsed.date_status == "invalid":
        result.freshness_status = "date_invalid"
        result.freshness_reason = f"日期格式无法解析：{parsed.raw_date}"
        result.should_default_select = False
        return result

    if parsed.date_status == "missing":
        result.freshness_status = "date_missing"
        result.freshness_reason = "未提供发布时间，无法确认是否在时间窗口内"
        result.should_default_select = False
        return result

    # 解析成功
    result.normalized_published_at = parsed.published_at or ""
    try:
        pub_dt = datetime.fromisoformat(
            result.normalized_published_at.replace("Z", "+00:00")
        )
    except Exception:
        result.freshness_status = "date_invalid"
        result.freshness_reason = f"标准化日期解析失败：{result.normalized_published_at}"
        result.should_default_select = False
        return result

    days_diff = (window_end - pub_dt).days
    result.days_from_search = max(0, days_diff)

    if pub_dt > window_end:
        result.freshness_status = "future_date"
        result.freshness_reason = f"发布时间 {pub_dt.date()} 晚于检索时间，疑似未来时间"
        result.should_default_select = False
    elif pub_dt >= window_start:
        result.freshness_status = "within_window"
        result.freshness_reason = f"发布于 {days_diff} 天前，符合 {time_window_days} 天窗口"
        result.should_default_select = True
    else:
        result.freshness_status = "outside_window"
        result.freshness_reason = (
            f"发布于 {days_diff} 天前，超出 {time_window_days} 天窗口"
            f"（最早 {window_start.date()}）"
        )
        result.should_default_select = False

    return result


def batch_check_freshness(
    records: list[dict],
    time_window_days: int,
    reference_time: Optional[datetime] = None,
) -> list[FreshnessResult]:
    """批量判断新鲜度，单条失败不中断。"""
    results = []
    for rec in records:
        try:
            results.append(check_freshness(rec, time_window_days, reference_time))
        except Exception as e:
            results.append(FreshnessResult(
                freshness_status="date_invalid",
                freshness_reason=f"新鲜度检查异常：{e}",
            ))
    return results


def freshness_summary(freshnesslist: list[FreshnessResult]) -> dict:
    """统计各状态数量。"""
    summary = {
        "within_window": 0,
        "outside_window": 0,
        "date_missing": 0,
        "date_invalid": 0,
        "future_date": 0,
    }
    for f in freshnesslist:
        key = f.freshness_status
        if key in summary:
            summary[key] += 1
    return summary
