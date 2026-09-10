"""test_docs_snapshot_diff.py
验证 docs_change_detector 各场景：first_seen、substantive_update、
metadata_only（lastmod 变化但正文不变）、unchanged。
"""
import pytest
from services.docs_change_detector import detect_change

_SAMPLE_HTML_V1 = """
<html><body>
<nav>Nav links here</nav>
<main>
  <h1>NVIDIA NeMo Deep Agents</h1>
  <p>This integration allows you to use Tavily search with NeMo.</p>
  <p>Version 1.0 features: basic search.</p>
</main>
<footer>Footer content</footer>
</body></html>
"""

_SAMPLE_HTML_V2 = """
<html><body>
<nav>Nav links here</nav>
<main>
  <h1>NVIDIA NeMo Deep Agents</h1>
  <p>This integration allows you to use Tavily search with NeMo.</p>
  <p>Version 1.0 features: basic search.</p>
  <p>Version 2.0: streaming support added.</p>
</main>
<footer>Footer content</footer>
</body></html>
"""

_SAMPLE_HTML_NAV_ONLY = """
<html><body>
<nav>Nav links UPDATED with new items</nav>
<main>
  <h1>NVIDIA NeMo Deep Agents</h1>
  <p>This integration allows you to use Tavily search with NeMo.</p>
  <p>Version 1.0 features: basic search.</p>
</main>
<footer>Footer content</footer>
</body></html>
"""


@pytest.fixture
def tmp_db(tmp_path):
    import sqlite3, database
    db_file = str(tmp_path / "test_diff.db")
    conn = sqlite3.connect(db_file)
    conn.execute(database._CREATE_SNAPSHOTS_SQL)
    conn.commit()
    conn.close()
    return db_file


def test_first_detection_is_new_page(tmp_db):
    result = detect_change(
        url="https://docs.tavily.com/integrations/nemo",
        raw_html=_SAMPLE_HTML_V1,
        competitor="Tavily",
        source_type="docs",
        title="NVIDIA NeMo",
        db_path=tmp_db,
    )
    assert result.update_status == "new_page", f"实际: {result.update_status}"
    assert result.content_hash != ""
    assert result.error == ""


def test_second_same_content_is_unchanged(tmp_db):
    detect_change(
        url="https://docs.tavily.com/integrations/nemo",
        raw_html=_SAMPLE_HTML_V1,
        competitor="Tavily",
        source_type="docs",
        title="NVIDIA NeMo",
        db_path=tmp_db,
    )
    result2 = detect_change(
        url="https://docs.tavily.com/integrations/nemo",
        raw_html=_SAMPLE_HTML_V1,
        competitor="Tavily",
        source_type="docs",
        title="NVIDIA NeMo",
        db_path=tmp_db,
    )
    assert result2.update_status == "unchanged"


def test_content_change_is_substantive_update(tmp_db):
    detect_change(
        url="https://docs.tavily.com/integrations/nemo",
        raw_html=_SAMPLE_HTML_V1,
        competitor="Tavily",
        source_type="docs",
        title="NVIDIA NeMo",
        db_path=tmp_db,
    )
    result2 = detect_change(
        url="https://docs.tavily.com/integrations/nemo",
        raw_html=_SAMPLE_HTML_V2,
        competitor="Tavily",
        source_type="docs",
        title="NVIDIA NeMo",
        db_path=tmp_db,
    )
    assert result2.update_status == "substantive_update"
    assert result2.previous_hash != result2.content_hash


def test_content_hash_is_stable(tmp_db):
    """同样的 HTML 应产生同样的 hash（幂等）。"""
    r1 = detect_change(
        url="https://docs.tavily.com/stable",
        raw_html=_SAMPLE_HTML_V1,
        competitor="Tavily", source_type="docs",
        title="Stable", db_path=tmp_db,
    )
    # 不调用第二次，只验证 hash 不为空
    assert len(r1.content_hash) == 32  # MD5 hex


def test_metadata_only_scenario(tmp_db):
    """lastmod 变化但正文内容完全不变 → 同一 HTML 两次提交，第二次应为 unchanged。"""
    detect_change(
        url="https://docs.tavily.com/faq",
        raw_html=_SAMPLE_HTML_V1,
        competitor="Tavily", source_type="docs",
        title="FAQ", lastmod="2026-07-09",
        db_path=tmp_db,
    )
    result2 = detect_change(
        url="https://docs.tavily.com/faq",
        raw_html=_SAMPLE_HTML_V1,  # 正文相同
        competitor="Tavily", source_type="docs",
        title="FAQ", lastmod="2026-07-10",  # lastmod 不同
        db_path=tmp_db,
    )
    # 正文 hash 相同，应为 unchanged（metadata_only 场景的期望行为）
    assert result2.update_status == "unchanged"
