"""Tests for URL encoding."""

from cymongoose import url_encode


def test_url_encode_basic():
    """Test basic URL encoding."""
    assert url_encode("hello world") == "hello%20world"
    assert url_encode("test@example.com") == "test%40example.com"


def test_url_encode_special_chars():
    """Test encoding of special characters."""
    # URL encoding may use lowercase hex digits
    assert url_encode("a+b").lower() == "a%2bb"
    assert url_encode("a&b=c").lower() == "a%26b%3dc"
    assert url_encode("100%").lower() == "100%25"


def test_url_encode_unicode():
    """Test encoding of Unicode characters."""
    result = url_encode("hello世界").lower()
    assert "hello" in result
    assert "%e4%b8%96%e7%95%8c" in result  # UTF-8 encoded (lowercase hex)


def test_url_encode_empty():
    """Test encoding empty string."""
    assert url_encode("") == ""


def test_url_encode_safe_chars():
    """Test that safe characters are not encoded."""
    assert url_encode("abc123") == "abc123"
    assert url_encode("test-file_name.txt") == "test-file_name.txt"
