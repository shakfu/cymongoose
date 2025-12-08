"""Tests for WebSocket functionality."""

import pytest
import threading
import time

try:
    import websocket

    HAS_WEBSOCKET = True
except ImportError:
    HAS_WEBSOCKET = False

from cymongoose import (
    Manager,
    MG_EV_WS_OPEN,
    MG_EV_WS_MSG,
    MG_EV_HTTP_MSG,
    WEBSOCKET_OP_TEXT,
    WEBSOCKET_OP_BINARY,
)
from .conftest import get_free_port

pytestmark = pytest.mark.skipif(
    not HAS_WEBSOCKET, reason="websocket-client not installed (pip install websocket-client)"
)


class TestWebSocketBasic:
    """Test basic WebSocket functionality."""

    def test_websocket_echo_text(self):
        """Test WebSocket text message echo."""
        received_messages = []
        stop = threading.Event()

        def handler(conn, event, data):
            if event == MG_EV_HTTP_MSG:
                # Upgrade HTTP connection to WebSocket
                conn.ws_upgrade(data)
            elif event == MG_EV_WS_MSG:
                received_messages.append(data.text)
                conn.ws_send(data.text, WEBSOCKET_OP_TEXT)

        manager = Manager(handler)
        port = get_free_port()
        manager.listen(f"http://0.0.0.0:{port}", http=True)

        def run_poll():
            while not stop.is_set():
                manager.poll(100)

        thread = threading.Thread(target=run_poll, daemon=True)
        thread.start()
        time.sleep(0.3)

        try:
            ws = websocket.WebSocket()
            ws.connect(f"ws://localhost:{port}/ws")

            # Send text message
            ws.send("Hello WebSocket")
            response = ws.recv()

            assert response == "Hello WebSocket"
            assert len(received_messages) > 0
            assert received_messages[0] == "Hello WebSocket"

            ws.close()
        finally:
            stop.set()
            thread.join(timeout=1)
            manager.close()

    def test_websocket_echo_binary(self):
        """Test WebSocket binary message echo."""
        received_messages = []
        stop = threading.Event()

        def handler(conn, event, data):
            if event == MG_EV_HTTP_MSG:
                conn.ws_upgrade(data)
            elif event == MG_EV_WS_MSG:
                received_messages.append(data.data)
                conn.ws_send(data.data, WEBSOCKET_OP_BINARY)

        manager = Manager(handler)
        port = get_free_port()
        manager.listen(f"http://0.0.0.0:{port}", http=True)

        def run_poll():
            while not stop.is_set():
                manager.poll(100)

        thread = threading.Thread(target=run_poll, daemon=True)
        thread.start()
        time.sleep(0.3)

        try:
            ws = websocket.WebSocket()
            ws.connect(f"ws://localhost:{port}/ws")

            # Send binary message
            test_data = b"\x00\x01\x02\x03\x04"
            ws.send(test_data, opcode=websocket.ABNF.OPCODE_BINARY)
            response = ws.recv()

            assert response == test_data
            assert len(received_messages) > 0
            assert received_messages[0] == test_data

            ws.close()
        finally:
            stop.set()
            thread.join(timeout=1)
            manager.close()

    def test_websocket_multiple_messages(self):
        """Test sending multiple WebSocket messages."""
        received_count = [0]
        stop = threading.Event()

        def handler(conn, event, data):
            if event == MG_EV_HTTP_MSG:
                conn.ws_upgrade(data)
            elif event == MG_EV_WS_MSG:
                received_count[0] += 1
                conn.ws_send(f"Echo {received_count[0]}: {data.text}")

        manager = Manager(handler)
        port = get_free_port()
        manager.listen(f"http://0.0.0.0:{port}", http=True)

        def run_poll():
            while not stop.is_set():
                manager.poll(100)

        thread = threading.Thread(target=run_poll, daemon=True)
        thread.start()
        time.sleep(0.3)

        try:
            ws = websocket.WebSocket()
            ws.connect(f"ws://localhost:{port}/ws")

            # Send multiple messages
            for i in range(3):
                ws.send(f"Message {i + 1}")
                response = ws.recv()
                assert f"Echo {i + 1}: Message {i + 1}" == response
                time.sleep(0.1)

            assert received_count[0] == 3

            ws.close()
        finally:
            stop.set()
            thread.join(timeout=1)
            manager.close()


class TestWebSocketHandshake:
    """Test WebSocket handshake and connection lifecycle."""

    def test_websocket_open_event(self):
        """Test MG_EV_WS_OPEN event fires on connection."""
        events = []
        stop = threading.Event()

        def handler(conn, event, data):
            events.append(event)
            if event == MG_EV_HTTP_MSG:
                conn.ws_upgrade(data)
            elif event == MG_EV_WS_MSG:
                conn.ws_send("pong")

        manager = Manager(handler)
        port = get_free_port()
        manager.listen(f"http://0.0.0.0:{port}", http=True)

        def run_poll():
            while not stop.is_set():
                manager.poll(100)

        thread = threading.Thread(target=run_poll, daemon=True)
        thread.start()
        time.sleep(0.3)

        try:
            ws = websocket.WebSocket()
            ws.connect(f"ws://localhost:{port}/ws")
            ws.send("ping")
            ws.recv()
            time.sleep(0.2)

            assert MG_EV_WS_OPEN in events

            ws.close()
        finally:
            stop.set()
            thread.join(timeout=1)
            manager.close()

    def test_websocket_connection_upgrade(self):
        """Test HTTP to WebSocket upgrade."""
        http_requests = [0]
        ws_connections = [0]
        stop = threading.Event()

        def handler(conn, event, data):
            if event == MG_EV_HTTP_MSG:
                http_requests[0] += 1
                conn.ws_upgrade(data)
            elif event == MG_EV_WS_OPEN:
                ws_connections[0] += 1
            elif event == MG_EV_WS_MSG:
                conn.ws_send("response")

        manager = Manager(handler)
        port = get_free_port()
        manager.listen(f"http://0.0.0.0:{port}", http=True)

        def run_poll():
            while not stop.is_set():
                manager.poll(100)

        thread = threading.Thread(target=run_poll, daemon=True)
        thread.start()
        time.sleep(0.3)

        try:
            ws = websocket.WebSocket()
            ws.connect(f"ws://localhost:{port}/ws")
            ws.send("test")
            ws.recv()
            time.sleep(0.2)

            # WebSocket upgrade involves HTTP request
            assert http_requests[0] > 0
            assert ws_connections[0] > 0

            ws.close()
        finally:
            stop.set()
            thread.join(timeout=1)
            manager.close()


class TestWebSocketMessage:
    """Test WsMessage data structure."""

    def test_ws_message_text_property(self):
        """Test WsMessage.text property."""
        received_data = {}
        stop = threading.Event()

        def handler(conn, event, data):
            if event == MG_EV_HTTP_MSG:
                conn.ws_upgrade(data)
            elif event == MG_EV_WS_MSG:
                received_data["text"] = data.text
                received_data["data"] = data.data
                received_data["flags"] = data.flags
                conn.ws_send("ok")

        manager = Manager(handler)
        port = get_free_port()
        manager.listen(f"http://0.0.0.0:{port}", http=True)

        def run_poll():
            while not stop.is_set():
                manager.poll(100)

        thread = threading.Thread(target=run_poll, daemon=True)
        thread.start()
        time.sleep(0.3)

        try:
            ws = websocket.WebSocket()
            ws.connect(f"ws://localhost:{port}/ws")

            test_message = "Hello, 世界!"
            ws.send(test_message)
            ws.recv()
            time.sleep(0.2)

            assert received_data["text"] == test_message
            assert isinstance(received_data["data"], bytes)
            assert isinstance(received_data["flags"], int)

            ws.close()
        finally:
            stop.set()
            thread.join(timeout=1)
            manager.close()

    def test_ws_message_binary_data(self):
        """Test WsMessage with binary data."""
        received_data = {}
        stop = threading.Event()

        def handler(conn, event, data):
            if event == MG_EV_HTTP_MSG:
                conn.ws_upgrade(data)
            elif event == MG_EV_WS_MSG:
                received_data["data"] = data.data
                conn.ws_send(data.data, WEBSOCKET_OP_BINARY)

        manager = Manager(handler)
        port = get_free_port()
        manager.listen(f"http://0.0.0.0:{port}", http=True)

        def run_poll():
            while not stop.is_set():
                manager.poll(100)

        thread = threading.Thread(target=run_poll, daemon=True)
        thread.start()
        time.sleep(0.3)

        try:
            ws = websocket.WebSocket()
            ws.connect(f"ws://localhost:{port}/ws")

            test_data = bytes([0, 1, 2, 3, 255, 254, 253])
            ws.send(test_data, opcode=websocket.ABNF.OPCODE_BINARY)
            response = ws.recv()
            time.sleep(0.2)

            assert received_data["data"] == test_data
            assert response == test_data

            ws.close()
        finally:
            stop.set()
            thread.join(timeout=1)
            manager.close()


class TestWebSocketOpcodes:
    """Test WebSocket operation codes."""

    def test_websocket_text_opcode(self):
        """Test WEBSOCKET_OP_TEXT constant."""
        assert WEBSOCKET_OP_TEXT == 1

    def test_websocket_binary_opcode(self):
        """Test WEBSOCKET_OP_BINARY constant."""
        assert WEBSOCKET_OP_BINARY == 2

    def test_ws_send_with_text_opcode(self):
        """Test ws_send with explicit text opcode."""
        sent_opcode = [None]
        stop = threading.Event()

        def handler(conn, event, data):
            if event == MG_EV_HTTP_MSG:
                conn.ws_upgrade(data)
            elif event == MG_EV_WS_MSG:
                sent_opcode[0] = WEBSOCKET_OP_TEXT
                conn.ws_send("response", WEBSOCKET_OP_TEXT)

        manager = Manager(handler)
        port = get_free_port()
        manager.listen(f"http://0.0.0.0:{port}", http=True)

        def run_poll():
            while not stop.is_set():
                manager.poll(100)

        thread = threading.Thread(target=run_poll, daemon=True)
        thread.start()
        time.sleep(0.3)

        try:
            ws = websocket.WebSocket()
            ws.connect(f"ws://localhost:{port}/ws")
            ws.send("test")
            response = ws.recv()
            time.sleep(0.2)

            assert sent_opcode[0] == WEBSOCKET_OP_TEXT
            assert response == "response"

            ws.close()
        finally:
            stop.set()
            thread.join(timeout=1)
            manager.close()
