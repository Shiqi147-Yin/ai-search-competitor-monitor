"""历史归档辅助服务"""
import database


def get_archive_stats() -> dict:
    """统计各周已确认数据量，返回 {week_id: count}。"""
    records = database.get_records({"review_status": "已确认"})
    stats: dict[str, int] = {}
    for rec in records:
        wid = rec.get("week_id") or "未知"
        stats[wid] = stats.get(wid, 0) + 1
    # 按周次降序排列
    return dict(sorted(stats.items(), reverse=True))
