"""测试：URL 规范化"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from services.url_normalizer import normalize_url, is_valid_url, deduplicate_urls


def test_strip_utm_params():
    url = "https://tavily.com/blog?utm_source=twitter&utm_medium=social&ref=abc"
    result = normalize_url(url)
    assert "utm_source" not in result
    assert "utm_medium" not in result
    assert "ref=" not in result
    assert "tavily.com" in result


def test_strip_ref_param():
    url = "https://exa.ai/blog/post?ref=newsletter&page=1"
    result = normalize_url(url)
    assert "ref=" not in result
    assert "page=1" in result  # 非追踪参数保留


def test_normalize_trailing_slash():
    a = normalize_url("https://tavily.com/blog/")
    b = normalize_url("https://tavily.com/blog")
    assert a == b


def test_same_url_different_tracking():
    """相同正文 URL 的不同追踪参数版本应被识别为相同。"""
    url1 = "https://tavily.com/blog/post?utm_source=a"
    url2 = "https://tavily.com/blog/post?utm_source=b&utm_medium=c"
    url3 = "https://tavily.com/blog/post"
    assert normalize_url(url1) == normalize_url(url2) == normalize_url(url3)


def test_different_paths_not_confused():
    """不同路径不能被误判为相同。"""
    a = normalize_url("https://exa.ai/blog/post-1")
    b = normalize_url("https://exa.ai/blog/post-2")
    assert a != b


def test_is_valid_url():
    assert is_valid_url("https://example.com")
    assert is_valid_url("http://tavily.com/blog")
    assert not is_valid_url("not-a-url")
    assert not is_valid_url("")
    assert not is_valid_url("ftp://example.com")


def test_deduplicate_urls():
    urls = [
        "https://tavily.com/blog?utm_source=a",
        "https://tavily.com/blog?utm_source=b",
        "https://exa.ai/blog",
    ]
    result = deduplicate_urls(urls)
    assert len(result) == 2
    assert "https://exa.ai/blog" in result
