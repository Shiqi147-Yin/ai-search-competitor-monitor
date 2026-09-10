"""Docs 页面快照存取服务
封装 official_source_snapshots 表的读写操作，供 docs_change_detector 使用。
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


_MAX_CONTENT_LEN = 50_000  # normalized_content 最大存储字符数


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def upsert_snapshot(
    competitor: str,
    source_url: str,
    source_type: str,
    page_role: str,
    title: str,
    content_hash: str,
    normalized_content: str,
    update_status: str,
    published_at: str = "",
    updated_at: str = "",
    raw_metadata: Optional[dict] = None,
    db_path=None,
) -> dict:
    """插入或更新快照。

    - 首次插入：写 first_seen_at、last_seen_at、last_checked_at
    - 再次更新：只改 last_seen_at、last_checked_at、content_hash、update_status
    Returns: {'action': 'inserted'|'updated', 'previous_hash': str}
    """
    now = _now_iso()
    content_truncated = normalized_content[:_MAX_CONTENT_LEN]
    metadata_str = json.dumps(raw_metadata or {})

    conn = _get_conn(db_path)
    try:
        existing = get_snapshot(competitor, source_url, db_path=db_path)
        if existing is None:
            conn.execute(
                """
                INSERT INTO official_source_snapshots
                  (competitor, source_url, source_type, page_role, title,
                   content_hash, normalized_content, update_status,
                   published_at, updated_at,
                   first_seen_at, last_seen_at, last_checked_at,
                   raw_metadata, is_active)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,1)
                """,
                (competitor, source_url, source_type, page_role, title,
                 content_hash, content_truncated, update_status,
                 published_at, updated_at,
                 now, now, now,
                 metadata_str),
            )
            conn.commit()
            return {"action": "inserted", "previous_hash": ""}
        else:
            prev_hash = existing["content_hash"]
            conn.execute(
                """
                UPDATE official_source_snapshots
                SET page_role=?, title=?, content_hash=?,
                    normalized_content=?, update_status=?,
                    published_at=?, updated_at=?,
                    last_seen_at=?, last_checked_at=?,
                    raw_metadata=?, is_active=1
                WHERE competitor=? AND source_url=?
                """,
                (page_role, title, content_hash,
                 content_truncated, update_status,
                 published_at, updated_at,
                 now, now,
                 metadata_str,
                 competitor, source_url),
            )
            conn.commit()
            return {"action": "updated", "previous_hash": prev_hash}
    finally:
        conn.close()


def get_snapshot(competitor: str, source_url: str, db_path=None) -> Optional[dict]:
    """读取单条快照，不存在返回 None。"""
    conn = _get_conn(db_path)
    try:
        row = conn.execute(
            "SELECT * FROM official_source_snapshots WHERE competitor=? AND source_url=?",
            (competitor, source_url),
        ).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def list_snapshots(
    competitor: str,
    source_type: Optional[str] = None,
    update_status: Optional[str] = None,
    db_path=None,
) -> list[dict]:
    """列出快照，支持按 source_type 和 update_status 过滤。"""
    conn = _get_conn(db_path)
    try:
        clauses = ["competitor=?"]
        params: list = [competitor]
        if source_type:
            clauses.append("source_type=?")
            params.append(source_type)
        if update_status:
            clauses.append("update_status=?")
            params.append(update_status)
        where = " AND ".join(clauses)
        rows = conn.execute(
            f"SELECT * FROM official_source_snapshots WHERE {where} ORDER BY last_seen_at DESC",
            params,
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def mark_inactive(competitor: str, source_url: str, db_path=None) -> None:
    """标记页面失效（is_active=0）。"""
    conn = _get_conn(db_path)
    try:
        conn.execute(
            "UPDATE official_source_snapshots SET is_active=0 WHERE competitor=? AND source_url=?",
            (competitor, source_url),
        )
        conn.commit()
    finally:
        conn.close()
