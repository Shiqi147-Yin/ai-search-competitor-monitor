"""测试：用本次抓取结果更新已有记录"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
from unittest.mock import patch


@pytest.fixture(autouse=True)
def isolated_db(tmp_path, monkeypatch):
    import config, database
    tmp_db = tmp_path / "update_refetch.db"
    monkeypatch.setattr(config, "DB_PATH", tmp_db)
    monkeypatch.setattr(database, "DB_PATH", tmp_db)
    database.init_db()
    database.migrate_db()
    yield


def _insert(url, fetch_status="failed", fetch_error="HTTP 451",
            competitor="Other", summary="人工摘要", priority="高"):
    import database
    from services.url_normalizer import normalize_url
    from datetime import datetime, timezone
    now = datetime.now(timezone.utc).isoformat()
    database.insert_record({
        "source_url": url, "normalized_url": normalize_url(url),
        "title": url, "competitor": competitor, "source_platform": "LinkedIn",
        "fetch_status": fetch_status, "fetch_error": fetch_error,
        "review_status": "待审核", "summary": summary, "priority": priority,
        "collected_at": now, "updated_at": now,
    })
    import database as db
    with db._get_conn() as conn:
        row = conn.execute("SELECT id FROM competitor_updates WHERE source_url=?", (url,)).fetchone()
    return row[0]


def _restricted_fetch(url):
    from services.url_fetcher import FetchResult
    return FetchResult(url=url, status="restricted", error="HTTP 451",
                       http_status_code=451, final_url=url)


def test_failed_updates_to_restricted():
    """failed 旧记录更新后 fetch_status = restricted。"""
    import database
    from services.refetch_comparator import fetch_and_compare, apply_refetch_result

    url = "https://linkedin.com/company/exa-ai"
    _insert(url)

    with patch("services.refetch_comparator.fetch_url", side_effect=_restricted_fetch):
        with patch("services.refetch_comparator.detect_both",
                   return_value={"competitor": "Exa", "source_platform": "LinkedIn"}):
            comp = fetch_and_compare(url)
            # apply 时内部会再次调 fetch_url
            with patch("services.refetch_comparator.fetch_url", side_effect=_restricted_fetch):
                result = apply_refetch_result(comp)

    assert result["ok"]
    updated = database.get_record_by_url(url)
    assert updated["fetch_status"] == "restricted"


def test_row_count_does_not_increase():
    """更新已有记录不新增数据库行。"""
    import database
    from services.refetch_comparator import fetch_and_compare, apply_refetch_result

    url = "https://linkedin.com/company/no-new-row"
    _insert(url)
    count_before = len(database.get_records())

    with patch("services.refetch_comparator.fetch_url", side_effect=_restricted_fetch):
        with patch("services.refetch_comparator.detect_both",
                   return_value={"competitor": "Exa", "source_platform": "LinkedIn"}):
            comp = fetch_and_compare(url)
            with patch("services.refetch_comparator.fetch_url", side_effect=_restricted_fetch):
                apply_refetch_result(comp)

    assert len(database.get_records()) == count_before


def test_fetch_error_preserved():
    """更新后 fetch_error 包含 HTTP 451。"""
    import database
    from services.refetch_comparator import fetch_and_compare, apply_refetch_result

    url = "https://linkedin.com/company/error-check"
    _insert(url)

    with patch("services.refetch_comparator.fetch_url", side_effect=_restricted_fetch):
        with patch("services.refetch_comparator.detect_both",
                   return_value={"competitor": "Exa", "source_platform": "LinkedIn"}):
            comp = fetch_and_compare(url)
            with patch("services.refetch_comparator.fetch_url", side_effect=_restricted_fetch):
                apply_refetch_result(comp)

    updated = database.get_record_by_url(url)
    assert "451" in (updated.get("fetch_error") or "")


def test_human_fields_not_overwritten():
    """更新不覆盖人工字段 summary、priority。"""
    import database
    from services.refetch_comparator import fetch_and_compare, apply_refetch_result

    url = "https://linkedin.com/company/protect-fields"
    _insert(url, summary="人工摘要", priority="高")

    with patch("services.refetch_comparator.fetch_url", side_effect=_restricted_fetch):
        with patch("services.refetch_comparator.detect_both",
                   return_value={"competitor": "Exa", "source_platform": "LinkedIn"}):
            comp = fetch_and_compare(url)
            with patch("services.refetch_comparator.fetch_url", side_effect=_restricted_fetch):
                apply_refetch_result(comp)

    updated = database.get_record_by_url(url)
    assert updated["summary"] == "人工摘要"
    assert updated["priority"] == "高"
