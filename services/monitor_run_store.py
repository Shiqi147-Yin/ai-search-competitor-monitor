"""巡检批次持久化服务
封装 official_monitor_runs 表的读写操作。
"""
import json
import sqlite3
from datetime import datetime, timezone
from typing import Optional

from config import DB_PATH


def _get_conn(db_path=None) -> sqlite3.Connection:
    path = db_path or str(DB_PATH)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    return conn


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def save_run(run: dict, db_path=None) -> int:
    """写入一条巡检批次记录，返回 run_id。"""
    columns = [
        "competitor", "window_start", "window_end", "source_types",
        "status", "blog_count", "docs_count", "github_count",
        "querit_count", "total_valid", "error_count", "result_json",
        "started_at", "completed_at",
    ]
    if "started_at" not in run:
        run = dict(run)
        run["started_at"] = _now_iso()

    present = {k: v for k, v in run.items() if k in columns}
    col_names = ", ".join(present.keys())
    placeholders = ", ".join(["?"] * len(present))
    values = list(present.values())

    conn = _get_conn(db_path)
    try:
        cursor = conn.execute(
            f"INSERT INTO official_monitor_runs ({col_names}) VALUES ({placeholders})",
            values,
        )
        conn.commit()
        return cursor.lastrowid
    finally:
        conn.close()


def update_run(run_id: int, updates: dict, db_path=None) -> None:
    """按列更新巡检批次记录。"""
    if not updates:
        return
    allowed = {
        "status", "blog_count", "docs_count", "github_count",
        "querit_count", "total_valid", "error_count", "result_json",
        "completed_at",
    }
    filtered = {k: v for k, v in updates.items() if k in allowed}
    if not filtered:
        return

    set_clause = ", ".join(f"{k}=?" for k in filtered)
    values = list(filtered.values()) + [run_id]

    conn = _get_conn(db_path)
    try:
        conn.execute(
            f"UPDATE official_monitor_runs SET {set_clause} WHERE id=?",
            values,
        )
        conn.commit()
    finally:
        conn.close()


def get_runs(competitor: Optional[str] = None, limit: int = 20, db_path=None) -> list[dict]:
    """列出巡检历史，按 started_at 倒序。"""
    conn = _get_conn(db_path)
    try:
        if competitor:
            rows = conn.execute(
                "SELECT * FROM official_monitor_runs WHERE competitor=? ORDER BY started_at DESC LIMIT ?",
                (competitor, limit),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM official_monitor_runs ORDER BY started_at DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def get_run_by_id(run_id: int, db_path=None) -> Optional[dict]:
    """按 ID 查询单条巡检记录。"""
    conn = _get_conn(db_path)
    try:
        row = conn.execute(
            "SELECT * FROM official_monitor_runs WHERE id=?", (run_id,)
        ).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()
