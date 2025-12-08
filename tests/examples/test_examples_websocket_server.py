#!/usr/bin/env python3
"""
Comprehensive tests for WebSocket server example.

Note: Some tests require the websocket-client package.
"""

import sys
import time
import threading
from pathlib import Path
import urllib.request
import pytest

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from cymongoose import (
    Manager,
    MG_EV_HTTP_MSG,
    MG_EV_WS_MSG,
    MG_EV_WS_OPEN,
    WEBSOCKET_OP_TEXT,
    WEBSOCKET_OP_BINARY,
)

# Check if websocket-client is available
try:
    from websocket import create_connection

    HAS_WS_CLIENT = True
except ImportError:
    HAS_WS_CLIENT = False


def test_websocket_server_http_endpoint():
    """Test that HTTP endpoints still work alongside WebSocket."""
    import json

    ws_clients = set()

    def handler(conn, event, data):
        if event == MG_EV_HTTP_MSG:
            if data.uri == "/api/stats":
                stats = {"websocket_clients": len(ws_clients)}
                conn.reply(200, json.dumps(stats), headers={"Content-Type": "application/json"})
            elif data.uri == "/ws":
                conn.ws_upgrade(data)
            else:
                conn.reply(200, "OK")
        elif event == MG_EV_WS_OPEN:
            ws_clients.add(conn)

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
        # Test HTTP endpoint
        response = urllib.request.urlopen(f"http://127.0.0.1:{port}/api/stats", timeout=2)
        assert response.status == 200
        data = json.loads(response.read().decode())
        assert "websocket_clients" in data
        assert data["websocket_clients"] == 0

    finally:
        stop.set()
        time.sleep(0.1)
        manager.close()


def test_websocket_server_static_files(tmp_path):
    """Test static file serving alongside WebSocket."""
    web_root = tmp_path / "web_root"
    web_root.mkdir()
    test_file = web_root / "test.html"
    test_file.write_text("<html><body>WebSocket Test</body></html>")

    def handler(conn, event, data):
        if event == MG_EV_HTTP_MSG:
            if data.uri == "/ws":
                conn.ws_upgrade(data)
            else:
                conn.serve_dir(data, root_dir=str(web_root))

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
        # Test static file
        response = urllib.request.urlopen(f"http://127.0.0.1:{port}/test.html", timeout=2)
        assert response.status == 200
        content = response.read().decode()
        assert "WebSocket Test" in content

    finally:
        stop.set()
        time.sleep(0.1)
        manager.close()


@pytest.mark.skipif(not HAS_WS_CLIENT, reason="websocket-client package not installed")
def test_websocket_server_echo():
    """Test WebSocket echo functionality."""
    messages_received = []

    def handler(conn, event, data):
        if event == MG_EV_HTTP_MSG and data.uri == "/ws":
            conn.ws_upgrade(data)
        elif event == MG_EV_WS_MSG:
            messages_received.append(data.text)
            # Echo back
            conn.ws_send(f"Echo: {data.text}", op=WEBSOCKET_OP_TEXT)

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
        # Connect WebSocket client
        ws = create_connection(f"ws://127.0.0.1:{port}/ws", timeout=5)

        # Send message
        ws.send("Hello Server")
        time.sleep(0.2)  # Wait for processing

        # Receive echo
        response = ws.recv()
        assert response == "Echo: Hello Server"
        assert "Hello Server" in messages_received

        ws.close()

    finally:
        stop.set()
        time.sleep(0.1)
        manager.close()


@pytest.mark.skipif(not HAS_WS_CLIENT, reason="websocket-client package not installed")
def test_websocket_server_binary():
    """Test WebSocket binary data handling."""
    messages_received = []

    def handler(conn, event, data):
        if event == MG_EV_HTTP_MSG and data.uri == "/ws":
            conn.ws_upgrade(data)
        elif event == MG_EV_WS_MSG:
            messages_received.append(data.data)
            # Echo back binary
            conn.ws_send(data.data, op=WEBSOCKET_OP_BINARY)

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
        # Connect WebSocket client
        ws = create_connection(f"ws://127.0.0.1:{port}/ws", timeout=5)

        # Send binary data
        binary_data = b"\x00\x01\x02\x03\xff"
        ws.send_binary(binary_data)
        time.sleep(0.2)

        # Receive echo
        response = ws.recv()
        assert response == binary_data
        assert binary_data in messages_received

        ws.close()

    finally:
        stop.set()
        time.sleep(0.1)
        manager.close()


@pytest.mark.skipif(not HAS_WS_CLIENT, reason="websocket-client package not installed")
def test_websocket_server_multiple_clients():
    """Test handling multiple WebSocket clients."""
    ws_clients = set()
    messages_by_client = {}

    def handler(conn, event, data):
        if event == MG_EV_HTTP_MSG and data.uri == "/ws":
            conn.ws_upgrade(data)
        elif event == MG_EV_WS_OPEN:
            ws_clients.add(conn)
            messages_by_client[id(conn)] = []
        elif event == MG_EV_WS_MSG:
            messages_by_client.setdefault(id(conn), []).append(data.text)
            conn.ws_send(f"Echo: {data.text}")

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
        time.sleep(0.1)
        ws2 = create_connection(f"ws://127.0.0.1:{port}/ws", timeout=5)
        time.sleep(0.1)

        # Send from each client
        ws1.send("Client 1 message")
        time.sleep(0.2)
        ws2.send("Client 2 message")
        time.sleep(0.2)

        # Receive responses
        resp1 = ws1.recv()
        resp2 = ws2.recv()

        assert resp1 == "Echo: Client 1 message"
        assert resp2 == "Echo: Client 2 message"
        assert len(ws_clients) == 2

        ws1.close()
        ws2.close()

    finally:
        stop.set()
        time.sleep(0.1)
        manager.close()


@pytest.mark.skipif(not HAS_WS_CLIENT, reason="websocket-client package not installed")
def test_websocket_server_broadcast():
    """Test broadcasting to all WebSocket clients."""
    import json

    ws_clients = set()

    def handler(conn, event, data):
        if event == MG_EV_HTTP_MSG:
            if data.uri == "/ws":
                conn.ws_upgrade(data)
            elif data.uri == "/api/broadcast" and data.method == "POST":
                message = data.body_text
                count = 0
                for ws_conn in list(ws_clients):
                    try:
                        ws_conn.ws_send(f"Broadcast: {message}")
                        count += 1
                    except:
                        pass
                conn.reply(200, f"Sent to {count} clients")
        elif event == MG_EV_WS_OPEN:
            ws_clients.add(conn)

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
        # Connect two WebSocket clients
        ws1 = create_connection(f"ws://127.0.0.1:{port}/ws", timeout=5)
        ws2 = create_connection(f"ws://127.0.0.1:{port}/ws", timeout=5)
        time.sleep(0.2)

        # Trigger broadcast via HTTP POST
        req = urllib.request.Request(
            f"http://127.0.0.1:{port}/api/broadcast", data=b"Test broadcast message", method="POST"
        )
        response = urllib.request.urlopen(req, timeout=2)
        assert response.status == 200

        time.sleep(0.2)

        # Both clients should receive the broadcast
        msg1 = ws1.recv()
        msg2 = ws2.recv()

        assert msg1 == "Broadcast: Test broadcast message"
        assert msg2 == "Broadcast: Test broadcast message"

        ws1.close()
        ws2.close()

    finally:
        stop.set()
        time.sleep(0.1)
        manager.close()
