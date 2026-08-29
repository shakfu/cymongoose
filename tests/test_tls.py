"""Tests for TLS configuration."""

import ssl
import subprocess
import time
from pathlib import Path

import pytest

from cymongoose import (
    MG_EV_ACCEPT,
    MG_EV_CONNECT,
    MG_EV_ERROR,
    MG_EV_HTTP_MSG,
    MG_EV_TLS_HS,
    Manager,
    TlsOpts,
)
from tests.conftest import get_free_port


def test_tls_opts_creation():
    """Test TlsOpts object creation."""
    opts = TlsOpts()
    assert opts.ca == b""
    assert opts.cert == b""
    assert opts.key == b""
    assert opts.name == b""
    assert not opts.skip_verification


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
    assert opts.skip_verification

    opts2 = TlsOpts(skip_verification=False)
    assert not opts2.skip_verification


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
        listener.tls_init(opts)
        manager.poll(10)

        assert listener.is_listening
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

        assert listener.is_listening
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

        assert listener.is_listening
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
        # Plain HTTP listener should not be TLS
        assert not listener.is_tls

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
    """Test that tls_init can be called multiple times (with tls_free between).

    Calling tls_init without tls_free first leaks the previous TLS context
    (mongoose does not free c->tls before overwriting it).
    """
    manager = Manager()

    try:
        listener = manager.listen("http://127.0.0.1:0")
        manager.poll(10)

        opts1 = TlsOpts(skip_verification=True)
        listener.tls_init(opts1)
        manager.poll(10)

        listener.tls_free()

        opts2 = TlsOpts(skip_verification=False)
        listener.tls_init(opts2)
        manager.poll(10)

        assert listener.is_listening
    finally:
        manager.close()


def test_tls_opts_none_values():
    """Test TlsOpts with None values."""
    opts = TlsOpts(ca=None, cert=None, key=None, name=None)
    assert opts.ca == b""
    assert opts.cert == b""
    assert opts.key == b""
    assert opts.name == b""


# ---------------------------------------------------------------------------
# TLS integration tests -- actual handshake with self-signed certificates
# ---------------------------------------------------------------------------


def _has_openssl():
    try:
        subprocess.run(["openssl", "version"], capture_output=True, check=True)
        return True
    except (FileNotFoundError, subprocess.CalledProcessError):
        return False


@pytest.fixture(scope="session")
def tls_certs(tmp_path_factory):
    """Generate a self-signed CA + server certificate for testing."""
    if not _has_openssl():
        pytest.skip("openssl not available")

    d = tmp_path_factory.mktemp("certs")

    # Mongoose built-in TLS only supports EC keys (P-256).
    # Keys must be in traditional PEM format ("EC PRIVATE KEY").

    # Generate CA EC key + self-signed cert
    subprocess.run(
        [
            "openssl",
            "ecparam",
            "-name",
            "prime256v1",
            "-genkey",
            "-noout",
            "-out",
            str(d / "ca.key"),
        ],
        capture_output=True,
        check=True,
    )
    subprocess.run(
        [
            "openssl",
            "req",
            "-x509",
            "-new",
            "-key",
            str(d / "ca.key"),
            "-out",
            str(d / "ca.crt"),
            "-days",
            "1",
            "-subj",
            "/CN=TestCA",
        ],
        capture_output=True,
        check=True,
    )

    # Generate server EC key + CSR
    subprocess.run(
        [
            "openssl",
            "ecparam",
            "-name",
            "prime256v1",
            "-genkey",
            "-noout",
            "-out",
            str(d / "server.key"),
        ],
        capture_output=True,
        check=True,
    )
    subprocess.run(
        [
            "openssl",
            "req",
            "-new",
            "-key",
            str(d / "server.key"),
            "-out",
            str(d / "server.csr"),
            "-subj",
            "/CN=localhost",
        ],
        capture_output=True,
        check=True,
    )

    # Sign server cert with CA
    subprocess.run(
        [
            "openssl",
            "x509",
            "-req",
            "-in",
            str(d / "server.csr"),
            "-CA",
            str(d / "ca.crt"),
            "-CAkey",
            str(d / "ca.key"),
            "-CAcreateserial",
            "-out",
            str(d / "server.crt"),
            "-days",
            "1",
        ],
        capture_output=True,
        check=True,
    )

    return {
        "ca_cert": (d / "ca.crt").read_bytes(),
        "server_cert": (d / "server.crt").read_bytes(),
        "server_key": (d / "server.key").read_bytes(),
    }


def _make_tls_server_handler(tls_certs, inner_handler):
    """Wrap a handler so that accepted connections get TLS initialized.

    Mongoose requires ``tls_init`` to be called on each accepted connection
    during ``MG_EV_ACCEPT`` (not on the listener itself).
    """
    from cymongoose import MG_EV_ACCEPT

    server_opts = TlsOpts(
        cert=tls_certs["server_cert"],
        key=tls_certs["server_key"],
    )

    def handler(conn, ev, data):
        if ev == MG_EV_ACCEPT:
            conn.tls_init(server_opts)
        inner_handler(conn, ev, data)

    return handler


def test_tls_https_handshake(tls_certs):
    """Test a full HTTPS handshake between server and client."""
    port = get_free_port()
    events = {"server_tls_hs": False, "client_tls_hs": False, "client_response": None}

    def server_logic(conn, ev, data):
        if ev == MG_EV_TLS_HS:
            events["server_tls_hs"] = True
        elif ev == MG_EV_HTTP_MSG:
            conn.reply(200, b"secure hello")

    def client_handler(conn, ev, data):
        if ev == MG_EV_CONNECT:
            conn.tls_init(
                TlsOpts(
                    ca=tls_certs["ca_cert"],
                    name=b"localhost",
                    skip_verification=True,
                )
            )
        elif ev == MG_EV_TLS_HS:
            events["client_tls_hs"] = True
            conn.send(b"GET / HTTP/1.1\r\nHost: localhost\r\n\r\n")
        elif ev == MG_EV_HTTP_MSG:
            events["client_response"] = data.body_bytes

    handler = _make_tls_server_handler(tls_certs, server_logic)
    mgr = Manager(handler)
    try:
        mgr.listen(f"https://127.0.0.1:{port}", http=True)
        mgr.poll(10)

        mgr.connect(
            f"https://127.0.0.1:{port}",
            handler=client_handler,
            http=True,
        )

        deadline = time.monotonic() + 10
        while events["client_response"] is None and time.monotonic() < deadline:
            mgr.poll(10)

        assert events["client_tls_hs"], "Client TLS handshake did not complete"
        assert events["client_response"] == b"secure hello"
    finally:
        mgr.close()


def test_tls_skip_verification_connects(tls_certs):
    """Client with skip_verification=True connects without CA cert."""
    port = get_free_port()
    events = {"client_response": None, "error": None}

    def server_logic(conn, ev, data):
        if ev == MG_EV_HTTP_MSG:
            conn.reply(200, b"no-ca-ok")

    def client_handler(conn, ev, data):
        if ev == MG_EV_CONNECT:
            # skip_verification skips CertificateVerify but mongoose
            # still checks hostname, so name must match cert CN.
            conn.tls_init(TlsOpts(skip_verification=True, name=b"localhost"))
        elif ev == MG_EV_TLS_HS:
            conn.send(b"GET / HTTP/1.1\r\nHost: localhost\r\n\r\n")
        elif ev == MG_EV_HTTP_MSG:
            events["client_response"] = data.body_bytes
        elif ev == MG_EV_ERROR:
            events["error"] = True

    handler = _make_tls_server_handler(tls_certs, server_logic)
    mgr = Manager(handler)
    try:
        mgr.listen(f"https://127.0.0.1:{port}", http=True)
        mgr.poll(10)

        mgr.connect(
            f"https://127.0.0.1:{port}",
            handler=client_handler,
            http=True,
        )

        deadline = time.monotonic() + 10
        while (
            events["client_response"] is None
            and events["error"] is None
            and time.monotonic() < deadline
        ):
            mgr.poll(10)

        assert events["client_response"] == b"no-ca-ok"
    finally:
        mgr.close()


def test_tls_is_tls_flag_set_after_handshake(tls_certs):
    """Verify is_tls is True on a connection after TLS handshake."""
    port = get_free_port()
    events = {"done": False, "client_is_tls": None}

    def server_logic(conn, ev, data):
        if ev == MG_EV_HTTP_MSG:
            conn.reply(200, b"ok")

    def client_handler(conn, ev, data):
        if ev == MG_EV_CONNECT:
            conn.tls_init(TlsOpts(skip_verification=True, name=b"localhost"))
        elif ev == MG_EV_TLS_HS:
            conn.send(b"GET / HTTP/1.1\r\nHost: localhost\r\n\r\n")
        elif ev == MG_EV_HTTP_MSG:
            events["client_is_tls"] = conn.is_tls
            events["done"] = True

    handler = _make_tls_server_handler(tls_certs, server_logic)
    mgr = Manager(handler)
    try:
        mgr.listen(f"https://127.0.0.1:{port}", http=True)
        mgr.poll(10)

        mgr.connect(
            f"https://127.0.0.1:{port}",
            handler=client_handler,
            http=True,
        )

        deadline = time.monotonic() + 10
        while not events["done"] and time.monotonic() < deadline:
            mgr.poll(10)

        assert events["done"], "Handshake + HTTP exchange did not complete"
        assert events["client_is_tls"] is True
    finally:
        mgr.close()


# --- Regression: short ECDSA r/s in a CA signature (patches/0001) -------------

CERT_DIR = Path(__file__).parent / "certs"


def _der_tlv(buf, i):
    """Read one DER TLV at offset i. Return (contents, offset after it)."""
    i += 1  # tag
    n = buf[i]
    i += 1
    if n & 0x80:
        k = n & 0x7F
        n = int.from_bytes(buf[i : i + k], "big")
        i += k
    return buf[i : i + n], i + n


def _ecdsa_rs_lengths(pem: bytes):
    """Return the encoded byte lengths of r and s in a cert's ECDSA signature."""
    der = ssl.PEM_cert_to_DER_cert(pem.decode())
    cert, _ = _der_tlv(der, 0)  # Certificate ::= SEQUENCE
    _, i = _der_tlv(cert, 0)  # tbsCertificate
    _, i = _der_tlv(cert, i)  # signatureAlgorithm
    sigbits, _ = _der_tlv(cert, i)  # signatureValue BIT STRING
    sig, _ = _der_tlv(sigbits[1:], 0)  # skip unused-bits octet; ECDSA-Sig-Value
    r, j = _der_tlv(sig, 0)
    s, _ = _der_tlv(sig, j)
    return len(r), len(s)


def test_short_sig_fixture_still_has_short_r_or_s():
    """Guard the fixture's defining property.

    If these certs are ever regenerated without preserving a short r or s,
    test_tls_verify_chain_with_short_sig below silently stops covering the bug.
    """
    r, s = _ecdsa_rs_lengths((CERT_DIR / "short_sig_server.crt").read_bytes())
    assert min(r, s) < 32, f"fixture no longer exercises the short case: r={r} s={s}"


def test_tls_verify_chain_with_short_sig():
    """Verify a chain whose CA signature has a short r or s.

    DER INTEGERs are minimally encoded, so r and s drop a leading zero byte
    about 1 time in 128. Mongoose's mg_tls_verify_cert_signature() left-aligned
    such values instead of left-padding them, so verification failed. Committed
    certs pin the case; a randomly generated pair hits it only ~0.8% of runs.
    See patches/0001-tls-pad-short-ecdsa-r-s.patch.
    """
    port = get_free_port()
    events = {"client_response": None, "error": None, "client_tls_hs": False}

    server_opts = TlsOpts(
        cert=(CERT_DIR / "short_sig_server.crt").read_bytes(),
        key=(CERT_DIR / "short_sig_server.key").read_bytes(),
    )

    def handler(conn, ev, data):
        if ev == MG_EV_ACCEPT:
            conn.tls_init(server_opts)
        elif ev == MG_EV_HTTP_MSG:
            conn.reply(200, b"short-sig ok")

    def client_handler(conn, ev, data):
        if ev == MG_EV_CONNECT:
            # No skip_verification: the CA signature over the leaf is checked.
            conn.tls_init(
                TlsOpts(
                    ca=(CERT_DIR / "short_sig_ca.crt").read_bytes(),
                    name=b"localhost",
                )
            )
        elif ev == MG_EV_TLS_HS:
            events["client_tls_hs"] = True
            conn.send(b"GET / HTTP/1.1\r\nHost: localhost\r\n\r\n")
        elif ev == MG_EV_HTTP_MSG:
            events["client_response"] = data.body_bytes
        elif ev == MG_EV_ERROR:
            events["error"] = repr(data)

    mgr = Manager(handler)
    try:
        mgr.listen(f"https://127.0.0.1:{port}", http=True)
        mgr.poll(10)

        mgr.connect(f"https://127.0.0.1:{port}", handler=client_handler, http=True)

        deadline = time.monotonic() + 10
        while (
            events["client_response"] is None
            and events["error"] is None
            and time.monotonic() < deadline
        ):
            mgr.poll(10)

        assert events["error"] is None, f"TLS error: {events['error']}"
        assert events["client_tls_hs"], "TLS handshake did not complete"
        assert events["client_response"] == b"short-sig ok"
    finally:
        mgr.close()
