"""测试：所有页面文件可编译，无 SyntaxError"""
import sys
import glob
import py_compile
from pathlib import Path

ROOT = Path(__file__).parent.parent


def _compile(rel_path: str) -> str | None:
    abs_path = ROOT / rel_path
    try:
        py_compile.compile(str(abs_path), doraise=True)
        return None
    except py_compile.PyCompileError as e:
        return str(e)


def test_app_py_compiles():
    err = _compile("app.py")
    assert err is None, f"app.py SyntaxError: {err}"


def test_page_import_compiles():
    err = _compile("pages/2_数据导入.py")
    assert err is None, f"pages/2_数据导入.py SyntaxError: {err}"


def test_page_dashboard_compiles():
    err = _compile("pages/1_本周看板.py")
    assert err is None, f"pages/1_本周看板.py SyntaxError: {err}"


def test_page_review_compiles():
    err = _compile("pages/3_待审核区.py")
    assert err is None, f"pages/3_待审核区.py SyntaxError: {err}"


def test_page_history_compiles():
    err = _compile("pages/4_历史动态.py")
    assert err is None, f"pages/4_历史动态.py SyntaxError: {err}"
