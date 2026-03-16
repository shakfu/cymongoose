"""Stress tests for connection churn and high-throughput scenarios.

These tests verify stability under load, catching use-after-free and
address-reuse bugs in the _connections dict.
"""

import socket
import threading
import time

from cymongoose import MG_EV_HTTP_MSG, Manager
from tests.conftest import get_free_port


def test_connection_churn_2000():
    """Open and close 2000 TCP connections in a tight loop.

    Verifies that rapid connection churn does not cause segfaults,
    stale entries in _connections, or address-reuse collisions.
    """
    port = get_free_port()
    accept_count = [0]

    def handler(conn, ev, data):
        if ev == MG_EV_HTTP_MSG:
            accept_count[0] += 1
            conn.reply(200, b"ok")

    manager = Manager(handler)
    manager.listen(f"http://127.0.0.1:{port}", http=True)

    stop = threading.Event()

    def poll_loop():
        while not stop.is_set():
            manager.poll(1)

    thread = threading.Thread(target=poll_loop, daemon=True)
    thread.start()
    time.sleep(0.1)

    errors = 0
    for i in range(2000):
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(2)
            sock.connect(("127.0.0.1", port))
            sock.sendall(b"GET / HTTP/1.1\r\nHost: localhost\r\n\r\n")
            sock.recv(1024)
            sock.close()
        except OSError:
            errors += 1

    stop.set()
    thread.join(timeout=3)
    manager.close()

    assert accept_count[0] >= 1900, f"Only {accept_count[0]}/2000 requests handled"
    assert errors < 100, f"Too many connection errors: {errors}"


def test_concurrent_connection_churn():
    """Multiple threads creating and destroying connections simultaneously."""
    port = get_free_port()
    request_count = [0]

    def handler(conn, ev, data):
        if ev == MG_EV_HTTP_MSG:
            request_count[0] += 1
            conn.reply(200, b"ok")

    manager = Manager(handler)
    manager.listen(f"http://127.0.0.1:{port}", http=True)

    stop = threading.Event()

    def poll_loop():
        while not stop.is_set():
            manager.poll(1)

    poll_thread = threading.Thread(target=poll_loop, daemon=True)
    poll_thread.start()
    time.sleep(0.1)

    errors = []

    def churn_worker(n):
        for _ in range(n):
            try:
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(2)
                sock.connect(("127.0.0.1", port))
                sock.sendall(b"GET / HTTP/1.1\r\nHost: localhost\r\n\r\n")
                sock.recv(1024)
                sock.close()
            except OSError as exc:
                errors.append(exc)

    threads = []
    for _ in range(5):
        t = threading.Thread(target=churn_worker, args=(400,))
        t.start()
        threads.append(t)

    for t in threads:
        t.join(timeout=30)

    stop.set()
    poll_thread.join(timeout=3)
    manager.close()

    total = 5 * 400
    assert request_count[0] >= total - 100, f"Only {request_count[0]}/{total} requests handled"
    assert len(errors) < 100, f"Too many errors: {len(errors)}"
