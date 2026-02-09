"""Tests for wakeup functionality."""

import pytest
import threading
import time
from cymongoose import Manager, MG_EV_WAKEUP, MG_EV_OPEN


def test_wakeup_basic():
    """Test basic wakeup notification."""
    manager = Manager(enable_wakeup=True)
    wakeup_received = []
    conn_id = None

    def handler(conn, ev, data):
        nonlocal conn_id
        if ev == MG_EV_OPEN and conn_id is None:
            conn_id = conn.id
        elif ev == MG_EV_WAKEUP:
            wakeup_received.append(data)

    try:
        # Create a listener to have a valid connection
        listener = manager.listen("tcp://127.0.0.1:0", handler=handler)
        manager.poll(10)

        # Get connection ID
        conn_id = listener.id

        # Send wakeup
        result = manager.wakeup(conn_id, b"test-wakeup-data")
        assert result is True

        # Poll to receive wakeup
        for _ in range(10):
            manager.poll(10)
            if wakeup_received:
                break

        assert len(wakeup_received) > 0
        assert wakeup_received[0] == b"test-wakeup-data"
    finally:
        manager.close()


def test_wakeup_empty_data():
    """Test wakeup with no data payload."""
    manager = Manager(enable_wakeup=True)
    wakeup_count = 0

    def handler(conn, ev, data):
        nonlocal wakeup_count
        if ev == MG_EV_WAKEUP:
            wakeup_count += 1
            assert data == b""

    try:
        listener = manager.listen("tcp://127.0.0.1:0", handler=handler)
        manager.poll(10)
        conn_id = listener.id

        # Send wakeup with empty data
        result = manager.wakeup(conn_id)
        assert result is True

        # Poll to receive
        for _ in range(10):
            manager.poll(10)

        assert wakeup_count > 0
    finally:
        manager.close()


def test_wakeup_from_thread():
    """Test wakeup from a different thread (thread-safe operation)."""
    manager = Manager(enable_wakeup=True)
    wakeup_received = []
    stop_polling = threading.Event()

    def handler(conn, ev, data):
        if ev == MG_EV_WAKEUP:
            wakeup_received.append(data)

    def poll_loop():
        """Background polling thread."""
        while not stop_polling.is_set():
            manager.poll(50)

    try:
        listener = manager.listen("tcp://127.0.0.1:0", handler=handler)
        manager.poll(10)
        conn_id = listener.id

        # Start polling in background thread
        poll_thread = threading.Thread(target=poll_loop, daemon=True)
        poll_thread.start()

        # Give polling thread time to start
        time.sleep(0.1)

        # Send wakeup from main thread
        result = manager.wakeup(conn_id, b"cross-thread-message")
        assert result is True

        # Wait for wakeup to be received
        time.sleep(0.2)

        assert len(wakeup_received) > 0
        assert wakeup_received[0] == b"cross-thread-message"
    finally:
        stop_polling.set()
        poll_thread.join(timeout=1)
        manager.close()


def test_wakeup_invalid_connection():
    """Test wakeup to non-existent connection ID."""
    manager = Manager(enable_wakeup=True)

    try:
        # Try to wake up a connection that doesn't exist
        result = manager.wakeup(999999, b"test")
        # May return False or True depending on Mongoose implementation
        # Just verify it doesn't crash
        assert result in (True, False)
    finally:
        manager.close()


def test_wakeup_without_init():
    """Test that wakeup fails if not initialized."""
    manager = Manager(enable_wakeup=False)

    try:
        listener = manager.listen("tcp://127.0.0.1:0")
        manager.poll(10)
        conn_id = listener.id

        # Wakeup should fail without initialization
        result = manager.wakeup(conn_id, b"test")
        assert result is False
    finally:
        manager.close()


def test_wakeup_multiple():
    """Test multiple wakeup calls."""
    manager = Manager(enable_wakeup=True)
    wakeup_data = []

    def handler(conn, ev, data):
        if ev == MG_EV_WAKEUP:
            wakeup_data.append(data)

    try:
        listener = manager.listen("tcp://127.0.0.1:0", handler=handler)
        manager.poll(10)
        conn_id = listener.id

        # Send multiple wakeups
        manager.wakeup(conn_id, b"message1")
        manager.wakeup(conn_id, b"message2")
        manager.wakeup(conn_id, b"message3")

        # Poll to receive all wakeups
        for _ in range(20):
            manager.poll(10)

        # Should have received all wakeups
        assert len(wakeup_data) >= 3
        assert b"message1" in wakeup_data
        assert b"message2" in wakeup_data
        assert b"message3" in wakeup_data
    finally:
        manager.close()
