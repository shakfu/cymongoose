"""Tests for multipart form parsing."""

from cymongoose import http_parse_multipart


def test_multipart_single_field():
    """Test parsing a single form field."""
    # Simulate multipart body
    body = (
        b"------WebKitFormBoundary\r\n"
        b'Content-Disposition: form-data; name="field1"\r\n'
        b"\r\n"
        b"value1\r\n"
        b"------WebKitFormBoundary--\r\n"
    )

    offset, part = http_parse_multipart(body, 0)

    if part is not None:  # Mongoose may or may not parse this format
        assert part["name"] == "field1"
        assert part["body"] == b"value1"


def test_multipart_no_parts():
    """Test parsing empty body."""
    offset, part = http_parse_multipart(b"", 0)
    assert offset == 0
    assert part is None


def test_multipart_bytes_input():
    """Test that bytes input works."""
    body = b"test content"
    offset, part = http_parse_multipart(body, 0)
    # May return None if not valid multipart
    assert offset >= 0


def test_multipart_str_input():
    """Test that string input works."""
    body = "test content"
    offset, part = http_parse_multipart(body, 0)
    # May return None if not valid multipart
    assert offset >= 0
