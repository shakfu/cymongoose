"""Tests for base64 encode/decode."""

import base64

import cymongoose as cm


class TestBase64Encode:
    def test_empty(self):
        assert cm.base64_encode(b"") == ""

    def test_hello(self):
        assert cm.base64_encode(b"hello") == base64.b64encode(b"hello").decode()

    def test_str_input(self):
        assert cm.base64_encode("hello") == base64.b64encode(b"hello").decode()

    def test_binary_data(self):
        data = bytes(range(256))
        assert cm.base64_encode(data) == base64.b64encode(data).decode()

    def test_padding_one(self):
        # 1 byte -> 4 chars with == padding
        result = cm.base64_encode(b"a")
        assert result == "YQ=="

    def test_padding_two(self):
        # 2 bytes -> 4 chars with = padding
        result = cm.base64_encode(b"ab")
        assert result == "YWI="

    def test_no_padding(self):
        # 3 bytes -> 4 chars, no padding
        result = cm.base64_encode(b"abc")
        assert result == "YWJj"


class TestBase64Decode:
    def test_empty(self):
        assert cm.base64_decode("") == b""

    def test_hello(self):
        encoded = base64.b64encode(b"hello").decode()
        assert cm.base64_decode(encoded) == b"hello"

    def test_binary_roundtrip(self):
        data = bytes(range(256))
        encoded = cm.base64_encode(data)
        assert cm.base64_decode(encoded) == data

    def test_with_padding(self):
        assert cm.base64_decode("YQ==") == b"a"
        assert cm.base64_decode("YWI=") == b"ab"
        assert cm.base64_decode("YWJj") == b"abc"
