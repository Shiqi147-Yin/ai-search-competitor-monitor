"""SQLite 数据库层：建表、增删改查、安全迁移"""
import sqlite3
from datetime import datetime, timezone
from typing import Any

from config import DB_PATH

# ── 建表 DDL ─────────────────────────────────────────────────

_CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS competitor_updates (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    publish_date    TEXT,
    collected_at    TEXT,
    competitor      TEXT,
    category        TEXT,
    title           TEXT NOT NULL,
    summary         TEXT,
    source_url      TEXT UNIQUE,
    source_platform TEXT,
    source_mode     TEXT,
    business_value  TEXT,
    querit_status   TEXT,
    gap_analysis    TEXT,
    suggested_action TEXT,
    priority        TEXT,
    review_status   TEXT,
    follow_up_status TEXT,
    week_id         TEXT,
    updated_at      TEXT
);
"""

_CREATE_BATCHES_SQL = """
CREATE TABLE IF NOT EXISTS import_batches (
    batch_id        TEXT PRIMARY KEY,
    created_at      TEXT,
    import_mode     TEXT,
    total           INTEGER DEFAULT 0,
    success         INTEGER DEFAULT 0,
    partial         INTEGER DEFAULT 0,
    failed          INTEGER DEFAULT 0,
    restricted      INTEGER DEFAULT 0,
    duplicate       INTEGER DEFAULT 0,
    final_imported  INTEGER DEFAULT 0
);
"""

# Phase 2 新增字段（列名, 类型, 默认值）
_PHASE2_COLUMNS = [
    ("fetch_status",                 "TEXT",    "'pending'"),
    ("fetch_error",                  "TEXT",    "NULL"),
    ("raw_title",                    "TEXT",    "NULL"),
    ("raw_content",                  "TEXT",    "NULL"),
    ("content_source",               "TEXT",    "NULL"),
    ("analysis_status",              "TEXT",    "'pending'"),
    ("imported_batch_id",            "TEXT",    "NULL"),
    ("manual_note",                  "TEXT",    "NULL"),
    ("normalized_url",               "TEXT",    "NULL"),
    ("final_url",                    "TEXT",    "NULL"),
    ("github_event_type",            "TEXT",    "NULL"),
    ("repository_name",              "TEXT",    "NULL"),
    ("changed_files",                "TEXT",    "NULL"),
    ("docs_changed",                 "INTEGER", "0"),
    ("capability_change",            "INTEGER", "0"),
    ("integration_change",           "INTEGER", "0"),
    ("developer_experience_change",  "INTEGER", "0"),
    ("change_summary",               "TEXT",    "NULL"),
    ("commit_or_release_url",        "TEXT",    "NULL"),
    # Phase 3 — 自动预分析字段
    ("secondary_tags",               "TEXT",    "NULL"),
    ("analysis_status",              "TEXT",    "'pending'"),
    ("analysis_confidence",          "REAL",    "0.0"),
    ("analysis_reason",              "TEXT",    "NULL"),
    ("auto_category",                "TEXT",    "NULL"),
    ("auto_business_value",          "TEXT",    "NULL"),
    ("auto_priority",                "TEXT",    "NULL"),
    ("auto_suggested_action",        "TEXT",    "NULL"),
    ("auto_querit_status",           "TEXT",    "'待评估'"),
    ("auto_gap_analysis",            "TEXT",    "NULL"),
    ("analyzed_at",                  "TEXT",    "NULL"),
    # Phase 4 — Querit API 检索字段
    ("querit_query",                 "TEXT",    "NULL"),
    ("querit_rank",                  "INTEGER", "0"),
    ("querit_score",                 "REAL",    "NULL"),
    ("querit_raw_summary",           "TEXT",    "NULL"),
    ("querit_raw_metadata",          "TEXT",    "NULL"),
    ("enrichment_status",            "TEXT",    "NULL"),
    # Phase 5 — 时间新鲜度字段（正式竞品记录）
    ("date_status",                  "TEXT",    "NULL"),
    ("date_source",                  "TEXT",    "NULL"),
    ("date_confidence",              "REAL",    "NULL"),
    # Phase 6 — 页面类型与下钻字段
    ("page_type",                    "TEXT",    "NULL"),
    ("is_entry_page",                "INTEGER", "0"),
    ("needs_drilldown",              "INTEGER", "0"),
    ("drilldown_status",             "TEXT",    "NULL"),
    ("parent_entry_url",             "TEXT",    "NULL"),
    ("discovery_method",             "TEXT",    "NULL"),
    ("import_eligible",              "INTEGER", "1"),
]

# ── Querit 检索专用表 DDL ─────────────────────────────────────

_CREATE_SEARCH_RUNS_SQL = """
CREATE TABLE IF NOT EXISTS querit_search_runs (
    id                   INTEGER PRIMARY KEY AUTOINCREMENT,
    started_at           TEXT,
    completed_at         TEXT,
    status               TEXT DEFAULT 'running',
    competitor_scope     TEXT,
    source_scope         TEXT,
    time_window_days     INTEGER DEFAULT 7,
    window_start         TEXT,
    window_end           TEXT,
    requested_result_count INTEGER DEFAULT 10,
    actual_result_count  INTEGER DEFAULT 0,
    unique_result_count  INTEGER DEFAULT 0,
    selected_result_count INTEGER DEFAULT 0,
    query_count          INTEGER DEFAULT 0,
    success_query_count  INTEGER DEFAULT 0,
    failed_query_count   INTEGER DEFAULT 0,
    within_window_count  INTEGER DEFAULT 0,
    outside_window_count INTEGER DEFAULT 0,
    missing_date_count   INTEGER DEFAULT 0,
    invalid_date_count   INTEGER DEFAULT 0,
    future_date_count    INTEGER DEFAULT 0,
    total_duration_ms    INTEGER DEFAULT 0,
    error_summary        TEXT,
    created_at           TEXT
);
"""

_CREATE_SEARCH_QUERIES_SQL = """
CREATE TABLE IF NOT EXISTS querit_search_queries (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id          INTEGER NOT NULL,
    generated_query TEXT,
    executed_query  TEXT,
    query_type      TEXT,
    competitor      TEXT,
    source_scope    TEXT,
    status          TEXT DEFAULT 'pending',
    result_count    INTEGER DEFAULT 0,
    duration_ms     INTEGER DEFAULT 0,
    error_message   TEXT,
    created_at      TEXT
);
"""

_CREATE_SEARCH_RESULTS_SQL = """
CREATE TABLE IF NOT EXISTS querit_search_results (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id              INTEGER NOT NULL,
    query_id            INTEGER,
    title               TEXT,
    source_url          TEXT,
    normalized_url      TEXT,
    raw_content         TEXT,
    raw_summary         TEXT,
    published_date      TEXT,
    score               REAL,
    rank                INTEGER DEFAULT 0,
    competitor          TEXT,
    source_platform     TEXT,
    duplicate           INTEGER DEFAULT 0,
    existing_record_id  INTEGER DEFAULT 0,
    possible_same_event INTEGER DEFAULT 0,
    selected            INTEGER DEFAULT 0,
    import_status       TEXT DEFAULT 'pending',
    raw_metadata        TEXT,
    -- Phase 5 时间新鲜度字段
    normalized_published_at  TEXT,
    raw_published_date       TEXT,
    date_status              TEXT DEFAULT 'missing',
    date_source              TEXT,
    date_confidence          REAL DEFAULT 0.0,
    freshness_status         TEXT DEFAULT 'date_missing',
    days_from_search         INTEGER,
    date_conflict            INTEGER DEFAULT 0,
    freshness_reason         TEXT,
    window_start             TEXT,
    window_end               TEXT,
    created_at          TEXT
);
"""


_CREATE_SNAPSHOTS_SQL = """
CREATE TABLE IF NOT EXISTS official_source_snapshots (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    competitor          TEXT NOT NULL,
    source_url          TEXT NOT NULL,
    source_type         TEXT NOT NULL,
    page_role           TEXT DEFAULT 'generic',
    title               TEXT DEFAULT '',
    content_hash        TEXT DEFAULT '',
    normalized_content  TEXT DEFAULT '',
    published_at        TEXT DEFAULT '',
    updated_at          TEXT DEFAULT '',
    first_seen_at       TEXT NOT NULL,
    last_seen_at        TEXT NOT NULL,
    last_checked_at     TEXT NOT NULL,
    update_status       TEXT DEFAULT 'first_seen',
    raw_metadata        TEXT DEFAULT '{}',
    is_active           INTEGER DEFAULT 1,
    UNIQUE(competitor, source_url)
);
"""

_CREATE_MONITOR_RUNS_SQL = """
CREATE TABLE IF NOT EXISTS official_monitor_runs (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    competitor      TEXT NOT NULL,
    window_start    TEXT NOT NULL,
    window_end      TEXT NOT NULL,
    source_types    TEXT DEFAULT 'all',
    status          TEXT DEFAULT 'running',
    blog_count      INTEGER DEFAULT 0,
    docs_count      INTEGER DEFAULT 0,
    github_count    INTEGER DEFAULT 0,
    querit_count    INTEGER DEFAULT 0,
    total_valid     INTEGER DEFAULT 0,
    error_count     INTEGER DEFAULT 0,
    result_json     TEXT DEFAULT '{}',
    started_at      TEXT NOT NULL,
    completed_at    TEXT DEFAULT ''
);
"""


def _get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    """首次启动时自动建表（幂等）。"""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with _get_conn() as conn:
        conn.execute(_CREATE_TABLE_SQL)
        conn.execute(_CREATE_BATCHES_SQL)
        conn.execute(_CREATE_SEARCH_RUNS_SQL)
        conn.execute(_CREATE_SEARCH_QUERIES_SQL)
        conn.execute(_CREATE_SEARCH_RESULTS_SQL)
        conn.execute(_CREATE_SNAPSHOTS_SQL)
        conn.execute(_CREATE_MONITOR_RUNS_SQL)
        conn.commit()


def get_table_columns(table_name: str) -> set[str]:
    """返回指定表的所有列名集合（表不存在返回空集）。"""
    try:
        with _get_conn() as conn:
            rows = conn.execute(f"PRAGMA table_info({table_name})").fetchall()
        return {r[1] for r in rows}
    except Exception:
        return set()


def add_column_if_missing(table_name: str, column_name: str, column_sql: str) -> bool:
    """如果列不存在，则 ALTER TABLE 添加；已存在时静默跳过。返回是否实际添加。"""
    existing = get_table_columns(table_name)
    if column_name in existing:
        return False
    try:
        with _get_conn() as conn:
            conn.execute(
                f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_sql}"
            )
            conn.commit()
        return True
    except sqlite3.OperationalError as e:
        # 极少数情况下并发重入，double-check
        if "duplicate column" in str(e).lower() or "already exists" in str(e).lower():
            return False
        import logging
        logging.getLogger(__name__).warning(
            "migrate: failed to add %s.%s: %s", table_name, column_name, e
        )
        return False


# ── 各表需要增量添加的字段 ─────────────────────────────────────

_SEARCH_RUNS_EXTRA_COLUMNS = [
    ("window_start",          "TEXT"),
    ("window_end",            "TEXT"),
    ("within_window_count",   "INTEGER DEFAULT 0"),
    ("outside_window_count",  "INTEGER DEFAULT 0"),
    ("missing_date_count",    "INTEGER DEFAULT 0"),
    ("invalid_date_count",    "INTEGER DEFAULT 0"),
    ("future_date_count",     "INTEGER DEFAULT 0"),
]

_SEARCH_RESULTS_EXTRA_COLUMNS = [
    ("normalized_published_at", "TEXT"),
    ("raw_published_date",      "TEXT"),
    ("date_status",             "TEXT DEFAULT 'missing'"),
    ("date_source",             "TEXT"),
    ("date_confidence",         "REAL DEFAULT 0.0"),
    ("freshness_status",        "TEXT DEFAULT 'date_missing'"),
    ("days_from_search",        "INTEGER"),
    ("date_conflict",           "INTEGER DEFAULT 0"),
    ("freshness_reason",        "TEXT"),
    ("window_start",            "TEXT"),
    ("window_end",              "TEXT"),
]

_COMPETITOR_UPDATES_FRESHNESS_COLUMNS = [
    ("date_status",     "TEXT"),
    ("date_source",     "TEXT"),
    ("date_confidence", "REAL"),
    # Phase 6 — 页面类型与下钻
    ("page_type",            "TEXT"),
    ("is_entry_page",        "INTEGER DEFAULT 0"),
    ("needs_drilldown",      "INTEGER DEFAULT 0"),
    ("drilldown_status",     "TEXT"),
    ("parent_entry_url",     "TEXT"),
    ("discovery_method",     "TEXT"),
    ("import_eligible",      "INTEGER DEFAULT 1"),
]


def run_migrations() -> None:
    """执行全部增量 migration，保证所有表字段完整。幂等，可重复执行。"""
    import logging
    log = logging.getLogger(__name__)

    init_db()  # 确保基础表存在

    # Phase 2/3 字段（competitor_updates）
    with _get_conn() as conn:
        for col_name, col_type, default in _PHASE2_COLUMNS:
            try:
                conn.execute(
                    f"ALTER TABLE competitor_updates ADD COLUMN {col_name} {col_type} DEFAULT {default}"
                )
            except sqlite3.OperationalError:
                pass
        conn.commit()

    # querit_search_runs 新鲜度统计字段
    for col, sql in _SEARCH_RUNS_EXTRA_COLUMNS:
        added = add_column_if_missing("querit_search_runs", col, sql)
        if added:
            log.debug("migration: added querit_search_runs.%s", col)

    # querit_search_results 新鲜度字段
    for col, sql in _SEARCH_RESULTS_EXTRA_COLUMNS:
        added = add_column_if_missing("querit_search_results", col, sql)
        if added:
            log.debug("migration: added querit_search_results.%s", col)

    # competitor_updates 新鲜度字段
    for col, sql in _COMPETITOR_UPDATES_FRESHNESS_COLUMNS:
        added = add_column_if_missing("competitor_updates", col, sql)
        if added:
            log.debug("migration: added competitor_updates.%s", col)

    # Phase 7 — 官方来源快照表（直接通过 init_db 的 CREATE TABLE IF NOT EXISTS 保证存在）
    init_db()


def migrate_db() -> None:
    """向后兼容别名，调用 run_migrations()。"""
    run_migrations()


# ── 写入 ──────────────────────────────────────────────────────

def insert_record(record: dict) -> str:
    """插入一条记录。
    返回值：'success' | 'duplicate' | 'error:<msg>'
    使用 normalized_url 做去重（优先），回退到 source_url。
    """
    # 所有已知列（原有 + Phase 2 + Phase 3 分析字段）
    columns = [
        "publish_date", "collected_at", "competitor", "category", "title",
        "summary", "source_url", "source_platform", "source_mode",
        "business_value", "querit_status", "gap_analysis", "suggested_action",
        "priority", "review_status", "follow_up_status", "week_id", "updated_at",
        # Phase 2
        "fetch_status", "fetch_error", "raw_title", "raw_content", "content_source",
        "analysis_status", "imported_batch_id", "manual_note", "normalized_url",
        "final_url", "github_event_type", "repository_name", "changed_files",
        "docs_changed", "capability_change", "integration_change",
        "developer_experience_change", "change_summary", "commit_or_release_url",
        # Phase 3
        "secondary_tags", "analysis_confidence", "analysis_reason",
        "auto_category", "auto_business_value", "auto_priority",
        "auto_suggested_action", "auto_querit_status", "auto_gap_analysis",
        "analyzed_at",
        # Phase 4 — Querit API
        "querit_query", "querit_rank", "querit_score",
        "querit_raw_summary", "querit_raw_metadata", "enrichment_status",
        # Phase 5 — freshness & date
        "date_status", "date_source", "date_confidence",
        # Phase 6 — page type & discovery
        "page_type", "is_entry_page", "needs_drilldown",
        "drilldown_status", "parent_entry_url", "discovery_method", "import_eligible",
    ]
    # 只插入 record 中实际存在的列，避免"NOT NULL"字段缺失
    present = {k: v for k, v in record.items() if k in columns}
    col_names = ", ".join(present.keys())
    placeholders = ", ".join(["?"] * len(present))
    values = list(present.values())
    sql = f"INSERT OR IGNORE INTO competitor_updates ({col_names}) VALUES ({placeholders})"

    try:
        with _get_conn() as conn:
            cursor = conn.execute(sql, values)
            conn.commit()
            if cursor.rowcount == 0:
                return "duplicate"
            return "success"
    except sqlite3.IntegrityError:
        return "duplicate"
    except Exception as e:
        return f"error:{e}"


def is_url_duplicate(normalized_url: str) -> bool:
    """检查 normalized_url 是否已在数据库中存在。"""
    with _get_conn() as conn:
        row = conn.execute(
            "SELECT id FROM competitor_updates WHERE normalized_url = ? OR source_url = ? LIMIT 1",
            (normalized_url, normalized_url),
        ).fetchone()
    return row is not None


# ── 查询 ──────────────────────────────────────────────────────

def get_records(filters: dict | None = None) -> list[dict]:
    """按条件查询记录，返回 list[dict]。

    支持的 filters key：
      week_id, competitor, category, review_status,
      source_platform, querit_status, priority,
      keyword（对 title/summary 做 LIKE 搜索），
      publish_date_start, publish_date_end
    """
    filters = filters or {}
    conditions = []
    params: list[Any] = []

    simple_eq = ["week_id", "competitor", "category", "review_status",
                 "source_platform", "querit_status", "priority"]
    for key in simple_eq:
        if filters.get(key):
            val = filters[key]
            if isinstance(val, list):
                placeholders = ",".join(["?"] * len(val))
                conditions.append(f"{key} IN ({placeholders})")
                params.extend(val)
            else:
                conditions.append(f"{key} = ?")
                params.append(val)

    if filters.get("keyword"):
        kw = f"%{filters['keyword']}%"
        conditions.append("(title LIKE ? OR summary LIKE ?)")
        params.extend([kw, kw])

    if filters.get("publish_date_start"):
        conditions.append("publish_date >= ?")
        params.append(filters["publish_date_start"])

    if filters.get("publish_date_end"):
        conditions.append("publish_date <= ?")
        params.append(filters["publish_date_end"])

    where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""
    sql = f"SELECT * FROM competitor_updates {where_clause} ORDER BY collected_at DESC"

    with _get_conn() as conn:
        rows = conn.execute(sql, params).fetchall()
    return [dict(r) for r in rows]


def get_all_week_ids() -> list[str]:
    """返回所有已存在的 week_id，降序排列。"""
    with _get_conn() as conn:
        rows = conn.execute(
            "SELECT DISTINCT week_id FROM competitor_updates WHERE week_id IS NOT NULL ORDER BY week_id DESC"
        ).fetchall()
    return [r[0] for r in rows]


def get_record_by_url(url: str) -> dict | None:
    """按 normalized_url 或 source_url 查询已有记录，返回 dict 或 None。"""
    with _get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM competitor_updates WHERE normalized_url = ? OR source_url = ? LIMIT 1",
            (url, url),
        ).fetchone()
    return dict(row) if row else None


# ── 更新 ──────────────────────────────────────────────────────

def update_record(record_id: int, fields: dict) -> bool:
    """更新指定记录的字段，自动刷新 updated_at。"""
    if not fields:
        return False
    fields = dict(fields)
    fields["updated_at"] = datetime.now(timezone.utc).isoformat()

    set_clause = ", ".join([f"{k} = ?" for k in fields])
    params = list(fields.values()) + [record_id]
    sql = f"UPDATE competitor_updates SET {set_clause} WHERE id = ?"

    try:
        with _get_conn() as conn:
            cursor = conn.execute(sql, params)
            conn.commit()
            return cursor.rowcount > 0
    except Exception:
        return False


# ── 批次记录 ──────────────────────────────────────────────────

def insert_batch_record(batch: dict) -> bool:
    """写入一条导入批次记录。"""
    cols = ["batch_id", "created_at", "import_mode", "total", "success",
            "partial", "failed", "restricted", "duplicate", "final_imported"]
    present = {k: v for k, v in batch.items() if k in cols}
    col_names = ", ".join(present.keys())
    placeholders = ", ".join(["?"] * len(present))
    sql = f"INSERT OR REPLACE INTO import_batches ({col_names}) VALUES ({placeholders})"
    try:
        with _get_conn() as conn:
            conn.execute(sql, list(present.values()))
            conn.commit()
        return True
    except Exception:
        return False


def get_batches() -> list[dict]:
    """返回所有导入批次，按创建时间倒序。"""
    with _get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM import_batches ORDER BY created_at DESC"
        ).fetchall()
    return [dict(r) for r in rows]


# ── Querit 检索专用 CRUD ──────────────────────────────────────

def create_search_run(run: dict) -> int:
    """创建一次检索运行记录，返回 run id。"""
    cols = [
        "started_at", "status", "competitor_scope", "source_scope",
        "time_window_days", "requested_result_count", "query_count", "created_at",
    ]
    present = {k: v for k, v in run.items() if k in cols}
    col_names = ", ".join(present.keys())
    placeholders = ", ".join(["?"] * len(present))
    sql = f"INSERT INTO querit_search_runs ({col_names}) VALUES ({placeholders})"
    with _get_conn() as conn:
        cur = conn.execute(sql, list(present.values()))
        conn.commit()
        return cur.lastrowid


def update_search_run(run_id: int, fields: dict) -> None:
    if not fields:
        return
    set_clause = ", ".join(f"{k} = ?" for k in fields)
    params = list(fields.values()) + [run_id]
    with _get_conn() as conn:
        conn.execute(f"UPDATE querit_search_runs SET {set_clause} WHERE id = ?", params)
        conn.commit()


def create_search_query(qry: dict) -> int:
    """记录一条检索 Query，返回 query id。"""
    cols = ["run_id", "generated_query", "executed_query", "query_type",
            "competitor", "source_scope", "status", "created_at"]
    present = {k: v for k, v in qry.items() if k in cols}
    col_names = ", ".join(present.keys())
    placeholders = ", ".join(["?"] * len(present))
    sql = f"INSERT INTO querit_search_queries ({col_names}) VALUES ({placeholders})"
    with _get_conn() as conn:
        cur = conn.execute(sql, list(present.values()))
        conn.commit()
        return cur.lastrowid


def update_search_query(query_id: int, fields: dict) -> None:
    if not fields:
        return
    set_clause = ", ".join(f"{k} = ?" for k in fields)
    params = list(fields.values()) + [query_id]
    with _get_conn() as conn:
        conn.execute(f"UPDATE querit_search_queries SET {set_clause} WHERE id = ?", params)
        conn.commit()


def insert_search_result(result: dict) -> int:
    """保存一条检索结果到预览表，返回 result id。"""
    cols = [
        "run_id", "query_id", "title", "source_url", "normalized_url",
        "raw_content", "raw_summary", "published_date", "score", "rank",
        "competitor", "source_platform", "duplicate", "existing_record_id",
        "possible_same_event", "selected", "import_status", "raw_metadata", "created_at",
    ]
    present = {k: v for k, v in result.items() if k in cols}
    col_names = ", ".join(present.keys())
    placeholders = ", ".join(["?"] * len(present))
    sql = f"INSERT INTO querit_search_results ({col_names}) VALUES ({placeholders})"
    with _get_conn() as conn:
        cur = conn.execute(sql, list(present.values()))
        conn.commit()
        return cur.lastrowid


def get_search_runs(limit: int = 20) -> list[dict]:
    """返回最近 N 次检索运行记录。"""
    with _get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM querit_search_runs ORDER BY id DESC LIMIT ?", (limit,)
        ).fetchall()
    return [dict(r) for r in rows]


def get_search_results(run_id: int) -> list[dict]:
    """返回指定 run_id 的全部结果。"""
    with _get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM querit_search_results WHERE run_id = ? ORDER BY rank ASC",
            (run_id,),
        ).fetchall()
    return [dict(r) for r in rows]
