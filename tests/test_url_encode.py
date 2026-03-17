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


# -- single-character truncation regression tests ----------------------------


def test_url_encode_single_space():
    """A single space should encode to '%20', not ''.

    Regression: buffer was sized as len*3+1 but mg_url_encode needs len*3+4.
    """
    assert url_encode(" ") == "%20"


def test_url_encode_single_percent():
    assert url_encode("%").lower() == "%25"


def test_url_encode_single_at():
    assert url_encode("@").lower() == "%40"


def test_url_encode_multibyte_utf8():
    """Multi-byte UTF-8 characters must encode correctly."""
    result = url_encode("\xe9").lower()  # e-acute, 2 bytes in UTF-8
    assert result == "%c3%a9"


def test_url_encode_all_special_single_chars():
    """Every single special character must produce a non-empty encoding."""
    for ch in " %&=+?#@!$'()*,;":
        encoded = url_encode(ch)
        assert encoded != "", f"url_encode({ch!r}) returned empty string"
        assert "%" in encoded, f"url_encode({ch!r}) = {encoded!r}, expected percent-encoding"
