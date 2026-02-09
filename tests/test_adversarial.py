"""Adversarial / negative tests for the HTTP server.

Uses raw sockets to send malformed data that urllib would never produce.
Each test verifies the server survives and can still serve valid requests.
"""

import socket
import time
import urllib.request

import pytest

try:
    import websocket

    HAS_WEBSOCKET = True
except ImportError:
    HAS_WEBSOCKET = False

from cymongoose import MG_EV_HTTP_MSG, MG_EV_WS_MSG, WEBSOCKET_OP_TEXT

from .conftest import ServerThread


def _simple_handler(conn, event, data):
    """Reply 200 with 'OK' to every HTTP request."""
    if event == MG_EV_HTTP_MSG:
        conn.reply(200, "OK")


def _ws_handler(conn, event, data):
    """Upgrade to WS if requested; otherwise reply 200 for healthcheck."""
    if event == MG_EV_HTTP_MSG:
        upgrade = data.header("Upgrade")
        if upgrade and upgrade.lower() == "websocket":
            conn.ws_upgrade(data)
        else:
            conn.reply(200, "OK")
    elif event == MG_EV_WS_MSG:
        conn.ws_send(data.text, WEBSOCKET_OP_TEXT)


def _check_server_alive(port, *, timeout=2):
    """Send a clean GET and assert a 200 response."""
    resp = urllib.request.urlopen(f"http://localhost:{port}/healthcheck", timeout=timeout)
    assert resp.status == 200
    body = resp.read().decode("utf-8")
    assert body == "OK"


def _raw_send(port, payload, *, recv=True, recv_size=4096, timeout=2):
    """Open a raw TCP socket, send payload bytes, optionally recv, then close."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(timeout)
    sock.connect(("127.0.0.1", port))
    if isinstance(payload, str):
        payload = payload.encode("utf-8")
    sock.sendall(payload)
    response = b""
    if recv:
        try:
            response = sock.recv(recv_size)
        except (socket.timeout, OSError):
            pass
    sock.close()
    return response


class TestMalformedRequests:
    """Test server resilience against malformed HTTP input."""

    def test_malformed_http_request_line(self):
        """Garbage that is not a valid HTTP request line."""
        with ServerThread(_simple_handler) as port:
            _raw_send(port, "NOT_HTTP garbage\r\n\r\n")
            time.sleep(0.2)
            _check_server_alive(port)

    def test_incomplete_http_request(self):
        """Headers never terminated -- client hangs up mid-request."""
        with ServerThread(_simple_handler) as port:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(2)
            sock.connect(("127.0.0.1", port))
            # Send partial request (no \r\n\r\n terminator)
            sock.sendall(b"GET / HTTP/1.1\r\nHost: localhost\r\n")
            time.sleep(0.3)
            sock.close()
            time.sleep(0.2)
            _check_server_alive(port)

    def test_invalid_http_method(self):
        """An HTTP method that no server should recognise."""
        with ServerThread(_simple_handler) as port:
            _raw_send(port, "XYZZY / HTTP/1.1\r\nHost: localhost\r\n\r\n")
            time.sleep(0.2)
            _check_server_alive(port)

    def test_oversized_header_line(self):
        """A single header value of ~100 KB."""
        with ServerThread(_simple_handler) as port:
            big_value = "X" * 100_000
            request = f"GET / HTTP/1.1\r\nHost: localhost\r\nX-Big: {big_value}\r\n\r\n"
            _raw_send(port, request)
            time.sleep(0.3)
            _check_server_alive(port)

    def test_many_headers(self):
        """500 distinct headers in a single request."""
        with ServerThread(_simple_handler) as port:
            headers = "".join(f"X-Hdr-{i}: value-{i}\r\n" for i in range(500))
            request = f"GET / HTTP/1.1\r\nHost: localhost\r\n{headers}\r\n"
            _raw_send(port, request)
            time.sleep(0.3)
            _check_server_alive(port)

    def test_null_bytes_in_request(self):
        """Null bytes embedded in the request URI."""
        with ServerThread(_simple_handler) as port:
            _raw_send(port, b"GET /\x00evil HTTP/1.1\r\nHost: localhost\r\n\r\n")
            time.sleep(0.2)
            _check_server_alive(port)

    def test_request_smuggling_double_content_length(self):
        """Two Content-Length headers with conflicting values."""
        with ServerThread(_simple_handler) as port:
            request = (
                "POST / HTTP/1.1\r\n"
                "Host: localhost\r\n"
                "Content-Length: 5\r\n"
                "Content-Length: 100\r\n"
                "\r\n"
                "hello"
            )
            _raw_send(port, request)
            time.sleep(0.3)
            _check_server_alive(port)


class TestConnectionAbuse:
    """Test server resilience against connection-level abuse."""

    def test_zero_byte_connection(self):
        """Open a socket and immediately close it (no data sent)."""
        with ServerThread(_simple_handler) as port:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(2)
            sock.connect(("127.0.0.1", port))
            sock.close()
            time.sleep(0.2)
            _check_server_alive(port)

    def test_connection_flood(self):
        """Open 50 sockets concurrently, send nothing, close after a brief pause."""
        with ServerThread(_simple_handler) as port:
            sockets = []
            for _ in range(50):
                s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                s.settimeout(2)
                try:
                    s.connect(("127.0.0.1", port))
                    sockets.append(s)
                except OSError:
                    s.close()
            time.sleep(0.5)
            for s in sockets:
                s.close()
            time.sleep(0.3)
            _check_server_alive(port)

    def test_slow_loris(self):
        """Send headers byte-by-byte with delays, then close without completing."""
        with ServerThread(_simple_handler) as port:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(5)
            sock.connect(("127.0.0.1", port))
            partial = b"GET / HTTP/1.1\r\nHost: localhost\r\n"
            for byte in partial:
                sock.sendall(bytes([byte]))
                time.sleep(0.01)
            # Never send the final \r\n -- just hang up
            sock.close()
            time.sleep(0.3)
            _check_server_alive(port)


@pytest.mark.skipif(not HAS_WEBSOCKET, reason="websocket-client not installed")
class TestWebSocketAdversarial:
    """Test server resilience against malformed WebSocket data."""

    def test_invalid_websocket_frame(self):
        """Send raw garbage bytes after a successful WS upgrade."""
        with ServerThread(_ws_handler) as port:
            ws = websocket.WebSocket()
            ws.connect(f"ws://localhost:{port}/ws")
            # Reach inside and send raw garbage on the underlying socket
            ws.sock.sendall(b"\xff\xfe\xfd\xfc\xfb\xfa")
            time.sleep(0.3)
            try:
                ws.close()
            except Exception:
                pass
            time.sleep(0.2)
            # Server should still serve HTTP
            _check_server_alive(port)

    def test_websocket_oversized_frame_header(self):
        """WS frame header claiming 1 GB payload, followed by close."""
        with ServerThread(_ws_handler) as port:
            ws = websocket.WebSocket()
            ws.connect(f"ws://localhost:{port}/ws")
            # Craft a binary frame header: FIN=1, opcode=2, mask=0,
            # 127 => 8-byte extended length = 1 GB
            frame = bytearray()
            frame.append(0x82)  # FIN + binary opcode
            frame.append(127)  # payload-length marker for 8-byte extended
            frame.extend((1 << 30).to_bytes(8, "big"))  # 1 GB
            try:
                ws.sock.sendall(bytes(frame))
            except OSError:
                pass
            time.sleep(0.3)
            try:
                ws.close()
            except Exception:
                pass
            time.sleep(0.2)
            _check_server_alive(port)
