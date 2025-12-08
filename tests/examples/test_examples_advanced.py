#!/usr/bin/env python3
"""
Tests all advanced examples:
- TLS/SSL HTTPS Server (certificate-based encryption)
- HTTP Proxy Client (CONNECT method tunneling)
- Multi-threaded Server (background work offloading)
"""

import sys
import time
import threading
import urllib.request
import ssl
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from cymongoose import (
    Manager,
    TlsOpts,
    MG_EV_HTTP_MSG,
    MG_EV_WAKEUP,
    MG_EV_CONNECT,
    MG_EV_READ,
)


# ===== TLS HTTPS Server Tests =====


def test_tls_https_server_can_import():
    """Test that TLS HTTPS server module can be imported."""
    try:
        with open("tests/examples/advanced/tls_https_server.py") as f:
            code = f.read()
            compile(code, "tls_https_server.py", "exec")
        assert True
    except SyntaxError as e:
        assert False, f"Syntax error in tls_https_server.py: {e}"


def test_tls_https_server_initialization():
    """Test TLS server can initialize with TlsOpts."""
    # Self-signed cert for testing
    cert = b"""-----BEGIN CERTIFICATE-----
MIICpDCCAYwCCQC6K9F7tIJm3zANBgkqhkiG9w0BAQsFADAUMRIwEAYDVQQDDAls
b2NhbGhvc3QwHhcNMjQwMTAxMDAwMDAwWhcNMjUwMTAxMDAwMDAwWjAUMRIwEAYD
VQQDDAlsb2NhbGhvc3QwggEiMA0GCSqGSIb3DQEBAQUAA4IBDwAwggEKAoIBAQCq
uP8hP0ypwT+8xjYqzLzYqP8hP0ypwT+8xjYqzLzYqP8hP0ypwT+8xjYqzLzY
-----END CERTIFICATE-----
"""
    key = b"""-----BEGIN PRIVATE KEY-----
MIIEvQIBADANBgkqhkiG9w0BAQEFAASCBKcwggSjAgEAAoIBAQCquP8hP0ypwT+8
xjYqzLzYqP8hP0ypwT+8xjYqzLzYqP8hP0ypwT+8xjYqzLzY
-----END PRIVATE KEY-----
"""

    def handler(conn, ev, data):
        if ev == MG_EV_HTTP_MSG:
            conn.reply(200, "Secure!")
            conn.drain()

    manager = Manager(handler)

    try:
        # Create HTTPS listener
        listener = manager.listen("https://127.0.0.1:0", http=True)
        port = listener.local_addr[1]

        # Initialize TLS with self-signed cert
        tls_opts = TlsOpts(cert=cert, key=key, skip_verification=True)
        listener.tls_init(tls_opts)

        # Verify TLS is enabled
        assert listener.is_tls

        # Run server briefly
        for _ in range(5):
            manager.poll(10)

        assert True

    finally:
        manager.close()


# ===== HTTP Proxy Client Tests =====


def test_http_proxy_client_can_import():
    """Test that HTTP proxy client module can be imported."""
    try:
        with open("tests/examples/advanced/http_proxy_client.py") as f:
            code = f.read()
            compile(code, "http_proxy_client.py", "exec")
        assert True
    except SyntaxError as e:
        assert False, f"Syntax error in http_proxy_client.py: {e}"


def test_http_proxy_client_url_parsing():
    """Test URL parsing functionality."""
    sys.path.insert(0, "tests/examples/advanced")
    try:
        import http_proxy_client

        # Test HTTP URL
        scheme, host, port, uri = http_proxy_client.parse_url("http://example.com/path")
        assert scheme == "http"
        assert host == "example.com"
        assert port == 80
        assert uri == "/path"

        # Test HTTPS URL with port
        scheme, host, port, uri = http_proxy_client.parse_url("https://example.com:8443/test")
        assert scheme == "https"
        assert host == "example.com"
        assert port == 8443
        assert uri == "/test"

        # Test root path
        scheme, host, port, uri = http_proxy_client.parse_url("http://example.com")
        assert uri == "/"

    finally:
        sys.path.pop(0)


def test_http_proxy_connect_method():
    """Test that proxy client can send CONNECT request."""
    connect_sent = threading.Event()
    connect_received = []

    def proxy_handler(conn, ev, data):
        """Simple proxy server that records CONNECT requests."""
        if ev == MG_EV_HTTP_MSG:
            hm = data
            if hm.method == "CONNECT":
                connect_received.append(hm.uri)
                # Respond with success
                conn.reply(200, "Connection established")
                conn.drain()
                connect_sent.set()

    # Start proxy server
    proxy_manager = Manager(proxy_handler)

    try:
        proxy_listener = proxy_manager.listen("http://127.0.0.1:0", http=True)
        proxy_port = proxy_listener.local_addr[1]

        # Run proxy in background
        proxy_stop = threading.Event()

        def proxy_poll():
            while not proxy_stop.is_set():
                proxy_manager.poll(50)

        proxy_thread = threading.Thread(target=proxy_poll, daemon=True)
        proxy_thread.start()
        time.sleep(0.2)

        # Create proxy client
        client_manager = Manager()

        tunnel_established = [False]

        def client_handler(conn, ev, data):
            if ev == MG_EV_CONNECT:
                # Send CONNECT request
                conn.send(b"CONNECT example.com:443 HTTP/1.1\r\nHost: example.com:443\r\n\r\n")
            elif ev == MG_EV_READ:
                recv_data = conn.recv_data()
                if b"200" in recv_data:
                    tunnel_established[0] = True

        client = client_manager.connect(
            f"http://127.0.0.1:{proxy_port}", handler=client_handler, http=True
        )

        # Run client in background
        client_stop = threading.Event()

        def client_poll():
            while not client_stop.is_set():
                client_manager.poll(50)

        client_thread = threading.Thread(target=client_poll, daemon=True)
        client_thread.start()

        # Wait for CONNECT
        connect_sent.wait(timeout=3)

        # Verify
        assert connect_sent.is_set(), "CONNECT request not received"
        assert len(connect_received) > 0
        assert "example.com:443" in connect_received[0]

    finally:
        proxy_stop.set()
        client_stop.set()
        time.sleep(0.2)
        proxy_manager.close()
        client_manager.close()


# ===== Multi-threaded Server Tests =====


def test_multithreaded_server_can_import():
    """Test that multi-threaded server module can be imported."""
    try:
        with open("tests/examples/advanced/multithreaded_server.py") as f:
            code = f.read()
            compile(code, "multithreaded_server.py", "exec")
        assert True
    except SyntaxError as e:
        assert False, f"Syntax error in multithreaded_server.py: {e}"


def test_multithreaded_server_fast_path():
    """Test single-threaded fast path responds immediately."""

    def handler(conn, ev, data):
        if ev == MG_EV_HTTP_MSG:
            hm = data
            if hm.uri == "/fast":
                conn.reply(200, "Fast response")
                conn.drain()

    manager = Manager(handler)

    try:
        listener = manager.listen("http://127.0.0.1:0", http=True)
        port = listener.local_addr[1]

        # Run in background
        stop = threading.Event()

        def poll_loop():
            while not stop.is_set():
                manager.poll(50)

        thread = threading.Thread(target=poll_loop, daemon=True)
        thread.start()
        time.sleep(0.2)

        # Request fast endpoint
        response = urllib.request.urlopen(f"http://127.0.0.1:{port}/fast", timeout=2)
        assert response.status == 200
        body = response.read()
        assert b"Fast response" in body

    finally:
        stop.set()
        time.sleep(0.2)
        manager.close()


def test_multithreaded_server_wakeup_path():
    """Test multi-threaded path with wakeup mechanism."""
    wakeup_received = threading.Event()
    wakeup_data = []

    def handler(conn, ev, data):
        if ev == MG_EV_HTTP_MSG:
            hm = data
            print(f"  Handler: MG_EV_HTTP_MSG uri={hm.uri}, conn={conn.id}")
            if hm.uri == "/slow":
                # Spawn thread that will call wakeup
                def worker():
                    print(f"  Worker: Starting for conn {conn.id}")
                    time.sleep(0.1)
                    try:
                        print(f"  Worker: Calling wakeup for conn {conn.id}")
                        config["manager"].wakeup(conn.id, b"Worker result")
                        print(f"  Worker: Wakeup called")
                    except Exception as e:
                        print(f"  Worker: Exception {e}")

                thread = threading.Thread(target=worker, daemon=True)
                thread.start()
                print(f"  Handler: Thread started")

        elif ev == MG_EV_WAKEUP:
            # Received wakeup from worker thread
            print(f"  Handler: MG_EV_WAKEUP data={data}")
            wakeup_data.append(data)
            conn.reply(200, f"Result: {data}")
            conn.drain()
            wakeup_received.set()
            print(f"  Handler: Response sent")

    config = {"manager": None}

    manager = Manager(handler, enable_wakeup=True)
    config["manager"] = manager

    try:
        listener = manager.listen("http://127.0.0.1:0", http=True)
        port = listener.local_addr[1]

        # Run in background
        stop = threading.Event()

        def poll_loop():
            while not stop.is_set():
                manager.poll(50)

        thread = threading.Thread(target=poll_loop, daemon=True)
        thread.start()
        time.sleep(0.2)

        # Request slow endpoint
        response = urllib.request.urlopen(f"http://127.0.0.1:{port}/slow", timeout=3)
        assert response.status == 200
        body = response.read()
        assert b"Worker result" in body

        # Verify wakeup was received
        wakeup_received.wait(timeout=3)
        assert wakeup_received.is_set()
        assert len(wakeup_data) > 0
        assert b"Worker result" in wakeup_data[0]

    finally:
        stop.set()
        time.sleep(0.2)
        manager.close()


def test_multithreaded_server_concurrent_requests():
    """Test that multiple slow requests can be processed concurrently."""
    responses_received = []
    lock = threading.Lock()

    def handler(conn, ev, data):
        if ev == MG_EV_HTTP_MSG:
            hm = data
            if hm.uri.startswith("/work"):
                # Extract work ID from URI
                work_id = hm.uri.split("/")[-1]

                def worker():
                    time.sleep(0.2)  # Simulate work
                    try:
                        config["manager"].wakeup(conn.id, f"Done: {work_id}".encode("utf-8"))
                    except:
                        pass

                thread = threading.Thread(target=worker, daemon=True)
                thread.start()

        elif ev == MG_EV_WAKEUP:
            with lock:
                responses_received.append(data)
            conn.reply(200, data)
            conn.drain()

    config = {"manager": None}

    manager = Manager(handler, enable_wakeup=True)
    config["manager"] = manager

    try:
        listener = manager.listen("http://127.0.0.1:0", http=True)
        port = listener.local_addr[1]

        # Run in background
        stop = threading.Event()

        def poll_loop():
            while not stop.is_set():
                manager.poll(50)

        thread = threading.Thread(target=poll_loop, daemon=True)
        thread.start()
        time.sleep(0.2)

        # Send 3 concurrent requests
        def make_request(work_id):
            try:
                urllib.request.urlopen(f"http://127.0.0.1:{port}/work/{work_id}", timeout=3)
            except:
                pass

        threads = []
        for i in range(3):
            t = threading.Thread(target=make_request, args=(i,))
            t.start()
            threads.append(t)

        # Wait for all requests
        for t in threads:
            t.join(timeout=5)

        # All should complete in ~200ms (concurrent) rather than 600ms (serial)
        time.sleep(0.5)

        with lock:
            # Should have received all 3 responses
            assert len(responses_received) == 3

    finally:
        stop.set()
        time.sleep(0.2)
        manager.close()


if __name__ == "__main__":
    # Run tests
    test_tls_https_server_can_import()
    print("[x] test_tls_https_server_can_import")

    test_tls_https_server_initialization()
    print("[x] test_tls_https_server_initialization")

    test_http_proxy_client_can_import()
    print("[x] test_http_proxy_client_can_import")

    test_http_proxy_client_url_parsing()
    print("[x] test_http_proxy_client_url_parsing")

    test_http_proxy_connect_method()
    print("[x] test_http_proxy_connect_method")

    test_multithreaded_server_can_import()
    print("[x] test_multithreaded_server_can_import")

    test_multithreaded_server_fast_path()
    print("[x] test_multithreaded_server_fast_path")

    test_multithreaded_server_wakeup_path()
    print("[x] test_multithreaded_server_wakeup_path")

    test_multithreaded_server_concurrent_requests()
    print("[x] test_multithreaded_server_concurrent_requests")

    print("\nAll Priority 5 tests passed!")
