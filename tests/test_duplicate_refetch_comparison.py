"""测试：重复记录新旧对比逻辑"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
from unittest.mock import patch


@pytest.fixture(autouse=True)
def isolated_db(tmp_path, monkeypatch):
    import config, database
    tmp_db = tmp_path / "compare_test.db"
    monkeypatch.setattr(config, "DB_PATH", tmp_db)
    monkeypatch.setattr(database, "DB_PATH", tmp_db)
    database.init_db()
    database.migrate_db()
    yield


def _insert_failed(url, competitor="Other", platform="LinkedIn"):
    import database
    from services.url_normalizer import normalize_url
    from datetime import datetime, timezone
    now = datetime.now(timezone.utc).isoformat()
    database.insert_record({
        "source_url": url,
        "normalized_url": normalize_url(url),
        "title": url,
        "competitor": competitor,
        "source_platform": platform,
        "fetch_status": "failed",
        "fetch_error": "HTTP 451",
        "review_status": "待审核",
        "collected_at": now,
        "updated_at": now,
    })


def _restricted_fetch(url):
    from services.url_fetcher import FetchResult
    return FetchResult(url=url, status="restricted", error="HTTP 451", http_status_code=451)


def test_comparison_returns_both_old_and_new():
    """返回旧记录和本次抓取结果，字段不混淆。"""
    from services.refetch_comparator import fetch_and_compare

    url = "https://linkedin.com/company/exa-ai"
    _insert_failed(url, competitor="Exa", platform="LinkedIn")

    with patch("services.refetch_comparator.fetch_url", side_effect=_restricted_fetch):
        comp = fetch_and_compare(url)

    assert comp is not None
    # 旧记录字段
    assert comp.existing_fetch_status == "failed"
    assert comp.existing_fetch_error == "HTTP 451"
    # 本次抓取字段
    assert comp.new_fetch_status == "restricted"
    assert "451" in comp.new_fetch_error


def test_old_and_new_fields_not_confused():
    """旧记录 competitor 和本次抓取 competitor 不互相覆盖。"""
    from services.refetch_comparator import fetch_and_compare

    url = "https://linkedin.com/company/tavily"
    _insert_failed(url, competitor="Other", platform="LinkedIn")

    def _tavily_fetch(u):
        from services.url_fetcher import FetchResult
        return FetchResult(url=u, status="restricted", error="HTTP 403", http_status_code=403)

    with patch("services.refetch_comparator.fetch_url", side_effect=_tavily_fetch):
        with patch("services.refetch_comparator.detect_both",
                   return_value={"competitor": "Tavily", "source_platform": "LinkedIn"}):
            comp = fetch_and_compare(url)

    # 旧记录是 Other，本次识别是 Tavily，不应相互污染
    assert comp.existing_competitor == "Other"
    assert comp.new_competitor == "Tavily"


def test_status_changed_flag():
    """旧 failed → 新 restricted，status_changed=True。"""
    from services.refetch_comparator import fetch_and_compare

    url = "https://linkedin.com/company/brave-software"
    _insert_failed(url)

    with patch("services.refetch_comparator.fetch_url", side_effect=_restricted_fetch):
        comp = fetch_and_compare(url)

    assert comp.status_changed is True
    assert "抓取失败" in comp.status_transition_msg
    assert "访问受限" in comp.status_transition_msg


def test_no_change_status_message():
    """旧状态和新状态相同时，显示'状态无变化'。"""
    from services.refetch_comparator import fetch_and_compare
    import database
    from services.url_normalizer import normalize_url
    from datetime import datetime, timezone

    url = "https://linkedin.com/company/no-change"
    now = datetime.now(timezone.utc).isoformat()
    database.insert_record({
        "source_url": url, "normalized_url": normalize_url(url),
        "title": "x", "fetch_status": "restricted",
        "fetch_error": "HTTP 403", "collected_at": now, "updated_at": now,
    })

    with patch("services.refetch_comparator.fetch_url", side_effect=_restricted_fetch):
        comp = fetch_and_compare(url)

    assert comp.status_changed is False
    assert "状态无变化" in comp.status_transition_msg
