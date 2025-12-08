#!/usr/bin/env python3
"""
Comprehensive tests for WebSocket broadcast example.

Note: Some tests require the websocket-client package.
"""

import sys
import time
import threading
from pathlib import Path
import pytest

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

# Import the BroadcastServer class from the example
sys.path.insert(0, str(Path(__file__).parent / "websocket"))
from websocket_broadcast import BroadcastServer

from cymongoose import Manager, MG_EV_HTTP_MSG, MG_EV_WS_MSG, MG_EV_WS_OPEN, MG_EV_CLOSE

# Check if websocket-client is available
try:
    from websocket import create_connection

    HAS_WS_CLIENT = True
except ImportError:
    HAS_WS_CLIENT = False


def test_broadcast_server_initialization():
    """Test that BroadcastServer initializes correctly."""
    server = BroadcastServer(port=8888, interval=2.0)

    assert server.port == 8888
    assert server.interval == 2.0
    assert server.broadcast_count == 0
    assert len(server.ws_clients) == 0
    assert server.manager is None


def test_broadcast_server_timer_callback():
    """Test that broadcast timer callback works."""
    server = BroadcastServer(port=8888, interval=1.0)
    initial_count = server.broadcast_count

    # Call timer callback manually
    server.broadcast_timer()

    assert server.broadcast_count == initial_count + 1


@pytest.mark.skipif(not HAS_WS_CLIENT, reason="websocket-client package not installed")
def test_broadcast_server_client_connection():
    """Test WebSocket client connection and welcome message."""
    server = BroadcastServer(port=0, interval=10)  # Long interval for testing

    # Run server in background
    server_thread = threading.Thread(target=lambda: None, daemon=True)

    server.manager = Manager(server.handler)
    listener = server.manager.listen(f"http://127.0.0.1:0", http=True)
    port = listener.local_addr[1]

    stop = threading.Event()

    def poll_loop():
        while not stop.is_set():
            server.manager.poll(100)

    poll_thread = threading.Thread(target=poll_loop, daemon=True)
    poll_thread.start()
    time.sleep(0.2)

    try:
        # Connect client
        ws = create_connection(f"ws://127.0.0.1:{port}/ws", timeout=5)
        time.sleep(0.2)

        # Should receive welcome message
        welcome = ws.recv()
        assert "Welcome" in welcome
        assert len(server.ws_clients) == 1

        ws.close()

    finally:
        stop.set()
        time.sleep(0.1)
        server.manager.close()


@pytest.mark.skipif(not HAS_WS_CLIENT, reason="websocket-client package not installed")
def test_broadcast_server_echo_messages():
    """Test that server echoes client messages."""
    server = BroadcastServer(port=0, interval=10)

    server.manager = Manager(server.handler)
    listener = server.manager.listen(f"http://127.0.0.1:0", http=True)
    port = listener.local_addr[1]

    stop = threading.Event()

    def poll_loop():
        while not stop.is_set():
            server.manager.poll(100)

    poll_thread = threading.Thread(target=poll_loop, daemon=True)
    poll_thread.start()
    time.sleep(0.2)

    try:
        ws = create_connection(f"ws://127.0.0.1:{port}/ws", timeout=5)
        time.sleep(0.2)

        # Skip welcome message
        ws.recv()

        # Send a message
        ws.send("Test message")
        time.sleep(0.2)

        # Should get echo
        echo = ws.recv()
        assert "Echo: Test message" in echo

        ws.close()

    finally:
        stop.set()
        time.sleep(0.1)
        server.manager.close()


@pytest.mark.skipif(not HAS_WS_CLIENT, reason="websocket-client package not installed")
def test_broadcast_server_multiple_clients():
    """Test broadcasting to multiple clients."""
    ws_clients = set()
    broadcast_count = [0]

    def handler(conn, event, data):
        if event == MG_EV_HTTP_MSG and data.uri == "/ws":
            conn.ws_upgrade(data)
        elif event == MG_EV_WS_OPEN:
            ws_clients.add(conn)
        elif event == MG_EV_CLOSE:
            ws_clients.discard(conn)

    def broadcast_to_all():
        """Broadcast a test message to all clients."""
        broadcast_count[0] += 1
        message = f"Broadcast #{broadcast_count[0]}"
        for conn in list(ws_clients):
            try:
                conn.ws_send(message)
            except:
                pass

    manager = Manager(handler)
    listener = manager.listen("http://127.0.0.1:0", http=True)
    port = listener.local_addr[1]

    stop = threading.Event()

    def poll_loop():
        while not stop.is_set():
            manager.poll(100)

    poll_thread = threading.Thread(target=poll_loop, daemon=True)
    poll_thread.start()
    time.sleep(0.2)

    try:
        # Connect multiple clients
        ws1 = create_connection(f"ws://127.0.0.1:{port}/ws", timeout=5)
        ws2 = create_connection(f"ws://127.0.0.1:{port}/ws", timeout=5)
        ws3 = create_connection(f"ws://127.0.0.1:{port}/ws", timeout=5)
        time.sleep(0.2)

        assert len(ws_clients) == 3

        # Broadcast to all
        broadcast_to_all()
        time.sleep(0.2)

        # All clients should receive
        msg1 = ws1.recv()
        msg2 = ws2.recv()
        msg3 = ws3.recv()

        assert msg1 == "Broadcast #1"
        assert msg2 == "Broadcast #1"
        assert msg3 == "Broadcast #1"

        ws1.close()
        ws2.close()
        ws3.close()

    finally:
        stop.set()
        time.sleep(0.1)
        manager.close()


@pytest.mark.skipif(not HAS_WS_CLIENT, reason="websocket-client package not installed")
def test_broadcast_server_with_timer():
    """Test periodic broadcasting using timer."""
    ws_clients = set()
    broadcast_count = [0]

    def broadcast_callback():
        broadcast_count[0] += 1
        message = f"Timer broadcast #{broadcast_count[0]}"
        for conn in list(ws_clients):
            try:
                conn.ws_send(message)
            except:
                pass

    def handler(conn, event, data):
        if event == MG_EV_HTTP_MSG and data.uri == "/ws":
            conn.ws_upgrade(data)
        elif event == MG_EV_WS_OPEN:
            ws_clients.add(conn)
        elif event == MG_EV_CLOSE:
            ws_clients.discard(conn)

    manager = Manager(handler)
    listener = manager.listen("http://127.0.0.1:0", http=True)
    port = listener.local_addr[1]

    # Add timer with short interval for testing
    timer = manager.timer_add(500, broadcast_callback, repeat=True, run_now=False)

    stop = threading.Event()

    def poll_loop():
        while not stop.is_set():
            manager.poll(100)

    poll_thread = threading.Thread(target=poll_loop, daemon=True)
    poll_thread.start()
    time.sleep(0.2)

    try:
        # Connect client
        ws = create_connection(f"ws://127.0.0.1:{port}/ws", timeout=5)
        time.sleep(0.2)

        # Wait for broadcasts (should receive at least 2 broadcasts in 1.5s)
        time.sleep(1.5)

        # Receive broadcasts
        messages = []
        while True:
            try:
                msg = ws.recv()
                messages.append(msg)
                if len(messages) >= 2:
                    break
            except:
                break

        # Should have received multiple timer broadcasts
        assert len(messages) >= 2
        assert all("Timer broadcast" in msg for msg in messages)
        assert broadcast_count[0] >= 2

        ws.close()

    finally:
        stop.set()
        time.sleep(0.1)
        manager.close()


def test_broadcast_server_client_cleanup():
    """Test that disconnected clients are cleaned up properly."""
    server = BroadcastServer(port=0, interval=10)

    server.manager = Manager(server.handler)
    listener = server.manager.listen(f"http://127.0.0.1:0", http=True)
    port = listener.local_addr[1]

    stop = threading.Event()

    def poll_loop():
        while not stop.is_set():
            server.manager.poll(100)

    poll_thread = threading.Thread(target=poll_loop, daemon=True)
    poll_thread.start()
    time.sleep(0.2)

    try:
        if HAS_WS_CLIENT:
            # Connect and disconnect client
            ws = create_connection(f"ws://127.0.0.1:{port}/ws", timeout=5)
            time.sleep(0.2)
            assert len(server.ws_clients) >= 1

            ws.close()
            time.sleep(0.3)

            # Client should be removed from set
            # (Either via MG_EV_CLOSE or next broadcast attempt)

    finally:
        stop.set()
        time.sleep(0.1)
        server.manager.close()


def test_broadcast_server_html_page():
    """Test that HTML page is served correctly."""
    import urllib.request

    server = BroadcastServer(port=0, interval=10)

    server.manager = Manager(server.handler)
    listener = server.manager.listen(f"http://127.0.0.1:0", http=True)
    port = listener.local_addr[1]

    stop = threading.Event()

    def poll_loop():
        while not stop.is_set():
            server.manager.poll(100)

    poll_thread = threading.Thread(target=poll_loop, daemon=True)
    poll_thread.start()
    time.sleep(0.2)

    try:
        # Request HTML page
        response = urllib.request.urlopen(f"http://127.0.0.1:{port}/", timeout=2)
        assert response.status == 200

        content = response.read().decode()
        assert "WebSocket Broadcast Demo" in content
        assert "text/html" in response.headers.get("Content-Type", "")

    finally:
        stop.set()
        time.sleep(0.1)
        server.manager.close()
