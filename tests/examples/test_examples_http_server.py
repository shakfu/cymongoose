#!/usr/bin/env python3
"""
Functional test for HTTP server example.
"""

import sys
import time
import threading
from pathlib import Path

import pytest

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from pymongoose import Manager, MG_EV_HTTP_MSG


def test_http_server():
    """Test basic HTTP server functionality."""
    received = []

    def handler(conn, event, data):
        if event == MG_EV_HTTP_MSG:
            received.append(data.uri)
            conn.reply(200, "OK")

    manager = Manager(handler)
    conn = manager.listen("http://127.0.0.1:0", http=True)  # Port 0 = random free port
    port = conn.local_addr[1]
    print(f"Server listening on port {port}")

    # Start polling in background
    stop = threading.Event()

    def poll_loop():
        while not stop.is_set():
            manager.poll(100)

    poll_thread = threading.Thread(target=poll_loop, daemon=True)
    poll_thread.start()

    # Give server time to start
    time.sleep(0.2)

    # Make test request
    import urllib.request

    try:
        response = urllib.request.urlopen(f"http://127.0.0.1:{port}/test", timeout=2)
        assert response.status == 200
        print("[x] HTTP server responded successfully")
    except Exception as e:
        print(f" Request failed: {e}")
        stop.set()
        poll_thread.join(timeout=1)
        manager.close()
        pytest.fail(f"Request failed: {e}")

    # Stop server
    stop.set()
    poll_thread.join(timeout=1)
    manager.close()

    # Verify request was received
    assert "/test" in received, f"Expected /test in {received}"
    print(f"[x] Server received request: {received}")


if __name__ == "__main__":
    import pytest as _pytest
    result = _pytest.main([__file__, "-v"])
    sys.exit(result)
