"""Tests for hashing utilities."""

import hashlib
import hmac

import cymongoose as cm


class TestMd5:
    def test_empty(self):
        assert cm.md5(b"") == hashlib.md5(b"").digest()

    def test_hello(self):
        assert cm.md5(b"hello") == hashlib.md5(b"hello").digest()

    def test_str_input(self):
        assert cm.md5("hello") == hashlib.md5(b"hello").digest()

    def test_length(self):
        assert len(cm.md5(b"test")) == 16


class TestSha1:
    def test_empty(self):
        assert cm.sha1(b"") == hashlib.sha1(b"").digest()

    def test_hello(self):
        assert cm.sha1(b"hello") == hashlib.sha1(b"hello").digest()

    def test_str_input(self):
        assert cm.sha1("hello") == hashlib.sha1(b"hello").digest()

    def test_length(self):
        assert len(cm.sha1(b"test")) == 20


class TestSha256:
    def test_empty(self):
        assert cm.sha256(b"") == hashlib.sha256(b"").digest()

    def test_hello(self):
        assert cm.sha256(b"hello") == hashlib.sha256(b"hello").digest()

    def test_str_input(self):
        assert cm.sha256("hello") == hashlib.sha256(b"hello").digest()

    def test_length(self):
        assert len(cm.sha256(b"test")) == 32

    def test_longer_data(self):
        data = b"a" * 1000
        assert cm.sha256(data) == hashlib.sha256(data).digest()


class TestHmacSha256:
    def test_basic(self):
        key = b"secret"
        data = b"message"
        expected = hmac.new(key, data, hashlib.sha256).digest()
        assert cm.hmac_sha256(key, data) == expected

    def test_str_inputs(self):
        expected = hmac.new(b"key", b"data", hashlib.sha256).digest()
        assert cm.hmac_sha256("key", "data") == expected

    def test_length(self):
        assert len(cm.hmac_sha256(b"k", b"d")) == 32

    def test_empty_data(self):
        expected = hmac.new(b"key", b"", hashlib.sha256).digest()
        assert cm.hmac_sha256(b"key", b"") == expected
