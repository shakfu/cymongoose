"""Tests for miscellaneous utility functions."""

import binascii

import cymongoose as cm


class TestMillis:
    def test_returns_positive(self):
        assert cm.millis() > 0

    def test_monotonic(self):
        a = cm.millis()
        b = cm.millis()
        assert b >= a


class TestRandomBytes:
    def test_length(self):
        assert len(cm.random_bytes(16)) == 16
        assert len(cm.random_bytes(32)) == 32

    def test_empty(self):
        assert cm.random_bytes(0) == b""

    def test_not_all_zeros(self):
        # Extremely unlikely for 32 random bytes to all be zero
        data = cm.random_bytes(32)
        assert data != b"\x00" * 32

    def test_different_calls(self):
        a = cm.random_bytes(32)
        b = cm.random_bytes(32)
        assert a != b  # vanishingly unlikely to collide


class TestRandomStr:
    def test_length(self):
        assert len(cm.random_str(10)) == 10
        assert len(cm.random_str(32)) == 32

    def test_empty(self):
        assert cm.random_str(0) == ""

    def test_alphanumeric(self):
        s = cm.random_str(100)
        assert s.isalnum()

    def test_different_calls(self):
        a = cm.random_str(32)
        b = cm.random_str(32)
        assert a != b


class TestCrc32:
    def test_empty(self):
        assert cm.crc32(b"") == binascii.crc32(b"")

    def test_hello(self):
        assert cm.crc32(b"hello") == binascii.crc32(b"hello") & 0xFFFFFFFF

    def test_str_input(self):
        assert cm.crc32("hello") == binascii.crc32(b"hello") & 0xFFFFFFFF

    def test_incremental(self):
        # CRC32 can be computed incrementally
        crc = cm.crc32(b"hel")
        crc = cm.crc32(b"lo", crc)
        assert crc == cm.crc32(b"hello")
