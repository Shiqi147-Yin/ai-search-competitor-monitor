"""test_docs_first_seen_bucket.py
验证 Nemo 类型（first_seen, high_value role）进入 docs_pending，不被 dropped。
"""
import pytest
from services.official_update_normalizer import OfficialUpdateItem
from services.official_monitor_importer import filter_valid_results

_WIN_START = "2026-07-08"
_WIN_END   = "2026-07-17"


def _nemo_item(update_status="new_page", within_window=True):
    return OfficialUpdateItem(
        competitor="Tavily",
        update_title="NVIDIA NeMo Deep Agents",
        source_channel="website_integration",
        source_url="https://docs.tavily.com/documentation/integrations/nemo-deepagents",
        published_at="",
        updated_at="2026-07-09T17:07:49.892Z",   # 真实日期：窗口内
        update_date="2026-07-09T17:07:49.892Z",
        within_window=within_window,
        is_entry_page=False,
        is_generic_page=False,
        update_status=update_status,
        docs_page_role="integration",
        import_eligible=True,
        discovery_method="official_docs_monitor",
    )


def test_nemo_new_page_within_window_goes_to_docs_valid():
    """within_window=True + new_page → docs_valid（eff_date 在窗口内）。"""
    fr = filter_valid_results(
        [_nemo_item(update_status="new_page", within_window=True)], [],
        window_start=_WIN_START, window_end=_WIN_END,
    )
    assert len(fr.docs_valid) == 1, f"docs_valid={len(fr.docs_valid)}, docs_pending={len(fr.docs_pending)}"
    assert len(fr.docs_pending) == 0


def test_nemo_unknown_within_window_goes_to_docs_pending():
    """status=unknown + high_value role + eff_date 在窗口内 → docs_pending。"""
    fr = filter_valid_results(
        [_nemo_item(update_status="unknown", within_window=True)], [],
        window_start=_WIN_START, window_end=_WIN_END,
    )
    assert len(fr.docs_pending) >= 1
    assert len(fr.docs_valid) == 0


def test_nemo_first_seen_within_window_goes_to_docs_pending():
    """update_status=first_seen + eff_date 在窗口内 → docs_pending。"""
    fr = filter_valid_results(
        [_nemo_item(update_status="first_seen", within_window=True)], [],
        window_start=_WIN_START, window_end=_WIN_END,
    )
    assert len(fr.docs_pending) >= 1


def test_nemo_not_dropped():
    """Nemo 不应该进入 outside_window（使用正确 effective_date）。"""
    for status in ("new_page", "first_seen", "unknown"):
        fr = filter_valid_results(
            [_nemo_item(update_status=status)], [],
            window_start=_WIN_START, window_end=_WIN_END,
        )
        in_valid_or_pending = len(fr.docs_valid) + len(fr.docs_pending)
        assert in_valid_or_pending >= 1, (
            f"status={status}: Nemo 不应被 dropped，"
            f"outside_window={len(fr.outside_window)}, "
            f"docs_valid={len(fr.docs_valid)}, docs_pending={len(fr.docs_pending)}"
        )


def test_debug_items_include_nemo():
    """debug_items 应包含 Nemo 的分桶记录。"""
    fr = filter_valid_results(
        [_nemo_item()], [],
        window_start=_WIN_START, window_end=_WIN_END,
    )
    nemo_dbg = [d for d in fr.debug_items if "nemo" in (d.source_url or "").lower()]
    assert len(nemo_dbg) == 1
    assert nemo_dbg[0].bucket in ("docs_valid", "docs_pending"), \
        f"Nemo bucket={nemo_dbg[0].bucket}, drop_reason={nemo_dbg[0].drop_reason}"

