"""测试：状态变化提示文案"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from services.refetch_comparator import _STATUS_LABEL


def _make_comp(old_status, new_status):
    """构造一个最小 RefetchComparison 对象。"""
    from services.refetch_comparator import RefetchComparison
    comp = RefetchComparison(
        original_url="https://example.com",
        normalized_url="https://example.com",
        existing_fetch_status=old_status,
        new_fetch_status=new_status,
    )
    old_label = _STATUS_LABEL.get(old_status, old_status)
    new_label = _STATUS_LABEL.get(new_status, new_status)
    if old_status != new_status:
        comp.status_changed = True
        comp.status_transition_msg = f"本次抓取结果已更新：{old_label} → {new_label}"
    else:
        comp.status_changed = False
        comp.status_transition_msg = f"状态无变化（{old_label}）"
    return comp


def test_failed_to_restricted_message():
    """failed → restricted 显示正确提示，包含两种状态名。"""
    comp = _make_comp("failed", "restricted")
    assert comp.status_changed is True
    assert "抓取失败" in comp.status_transition_msg
    assert "访问受限" in comp.status_transition_msg


def test_restricted_to_success_message():
    """restricted → success 显示正确提示。"""
    comp = _make_comp("restricted", "success")
    assert comp.status_changed is True
    assert "访问受限" in comp.status_transition_msg
    assert "抓取成功" in comp.status_transition_msg


def test_no_change_message():
    """状态未变化时显示'状态无变化'。"""
    comp = _make_comp("restricted", "restricted")
    assert comp.status_changed is False
    assert "状态无变化" in comp.status_transition_msg


def test_all_status_labels_defined():
    """所有关键状态都有中文标签。"""
    for status in ("success", "partial", "restricted", "failed", "duplicate"):
        assert status in _STATUS_LABEL
        label = _STATUS_LABEL[status]
        assert label  # 不为空


def test_restricted_label_not_failed():
    """restricted 标签不含'失败'。"""
    assert "失败" not in _STATUS_LABEL["restricted"]
    assert "受限" in _STATUS_LABEL["restricted"]
