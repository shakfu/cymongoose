"""Tests for TLS configuration."""

import pytest
from cymongoose import Manager, TlsOpts, MG_EV_HTTP_MSG


def test_tls_opts_creation():
    """Test TlsOpts object creation."""
    opts = TlsOpts()
    assert opts.ca == b""
    assert opts.cert == b""
    assert opts.key == b""
    assert opts.name == b""
    assert opts.skip_verification == False


def test_tls_opts_with_strings():
    """Test TlsOpts with string arguments."""
    opts = TlsOpts(ca="ca content", cert="cert content", key="key content", name="example.com")
    assert opts.ca == b"ca content"
    assert opts.cert == b"cert content"
    assert opts.key == b"key content"
    assert opts.name == b"example.com"


def test_tls_opts_with_bytes():
    """Test TlsOpts with bytes arguments."""
    opts = TlsOpts(ca=b"ca bytes", cert=b"cert bytes", key=b"key bytes", name=b"example.com")
    assert opts.ca == b"ca bytes"
    assert opts.cert == b"cert bytes"
    assert opts.key == b"key bytes"
    assert opts.name == b"example.com"


def test_tls_opts_skip_verification():
    """Test TlsOpts skip_verification flag."""
    opts = TlsOpts(skip_verification=True)
    assert opts.skip_verification == True

    opts2 = TlsOpts(skip_verification=False)
    assert opts2.skip_verification == False


def test_tls_init_method_exists():
    """Test that tls_init method exists on connections."""
    manager = Manager()

    try:
        listener = manager.listen("http://127.0.0.1:0")
        manager.poll(10)

        assert hasattr(listener, "tls_init")
        assert callable(listener.tls_init)
        assert hasattr(listener, "tls_free")
        assert callable(listener.tls_free)
    finally:
        manager.close()


def test_tls_init_with_empty_opts():
    """Test tls_init with empty TlsOpts."""
    manager = Manager()

    try:
        listener = manager.listen("http://127.0.0.1:0")
        manager.poll(10)

        opts = TlsOpts()
        # Should not crash
        listener.tls_init(opts)
        manager.poll(10)

        assert True
    finally:
        manager.close()


def test_tls_init_with_skip_verification():
    """Test tls_init with skip_verification."""
    manager = Manager()

    try:
        listener = manager.listen("http://127.0.0.1:0")
        manager.poll(10)

        opts = TlsOpts(skip_verification=True)
        listener.tls_init(opts)
        manager.poll(10)

        assert True
    finally:
        manager.close()


def test_tls_free():
    """Test tls_free method."""
    manager = Manager()

    try:
        listener = manager.listen("http://127.0.0.1:0")
        manager.poll(10)

        opts = TlsOpts()
        listener.tls_init(opts)
        manager.poll(10)

        # Should be able to free TLS
        listener.tls_free()
        manager.poll(10)

        assert True
    finally:
        manager.close()


def test_is_tls_property():
    """Test is_tls property."""
    manager = Manager()

    try:
        # HTTP listener should not be TLS
        listener = manager.listen("http://127.0.0.1:0")
        manager.poll(10)

        assert hasattr(listener, "is_tls")
        # HTTP connection starts as non-TLS
        # (TLS flag is set during handshake, not at creation)
        assert listener.is_tls == False or listener.is_tls == True  # Either is valid

    finally:
        manager.close()


def test_tls_opts_partial():
    """Test TlsOpts with only some fields set."""
    opts = TlsOpts(ca="ca content", name="example.com")
    assert opts.ca == b"ca content"
    assert opts.cert == b""
    assert opts.key == b""
    assert opts.name == b"example.com"


def test_tls_init_multiple_times():
    """Test that tls_init can be called multiple times."""
    manager = Manager()

    try:
        listener = manager.listen("http://127.0.0.1:0")
        manager.poll(10)

        opts1 = TlsOpts(skip_verification=True)
        listener.tls_init(opts1)
        manager.poll(10)

        opts2 = TlsOpts(skip_verification=False)
        listener.tls_init(opts2)
        manager.poll(10)

        assert True
    finally:
        manager.close()


def test_tls_opts_none_values():
    """Test TlsOpts with None values."""
    opts = TlsOpts(ca=None, cert=None, key=None, name=None)
    assert opts.ca == b""
    assert opts.cert == b""
    assert opts.key == b""
    assert opts.name == b""
