"""Tests for SNTP (time synchronization)."""

import time

import pytest

from cymongoose import MG_EV_SNTP_TIME, Manager


def test_sntp_connect():
    """Test SNTP connection creation."""
    manager = Manager()

    try:
        # Connect to a public SNTP server
        conn = manager.sntp_connect("udp://time.google.com:123")
        manager.poll(10)

        # Connection should be created
        assert conn is not None
        assert conn.is_udp
    finally:
        manager.close()


def test_sntp_request():
    """Test SNTP time request."""
    manager = Manager()
    time_received = []

    def handler(conn, ev, data):
        if ev == MG_EV_SNTP_TIME:
            time_received.append(data)

    try:
        # Connect to SNTP server
        conn = manager.sntp_connect("udp://time.google.com:123", handler=handler)
        manager.poll(10)

        # Send time request
        conn.sntp_request()

        # Poll for response (may take a while)
        for _ in range(100):
            manager.poll(50)
            if time_received:
                break
            time.sleep(0.01)

        # SNTP requires UDP port 123 which may be blocked in CI
        if not time_received:
            pytest.skip("SNTP server did not respond (network may be unavailable)")
        assert len(time_received) > 0
    finally:
        manager.close()


def test_sntp_time_format():
    """Test that SNTP time is in correct format (milliseconds since epoch)."""
    manager = Manager()
    time_received = []

    def handler(conn, ev, data):
        if ev == MG_EV_SNTP_TIME:
            time_received.append(data)

    try:
        conn = manager.sntp_connect("udp://time.google.com:123", handler=handler)
        manager.poll(10)

        conn.sntp_request()

        # Poll for response
        for _ in range(100):
            manager.poll(50)
            if time_received:
                break
            time.sleep(0.01)

        # SNTP requires UDP port 123 which may be blocked in CI
        if not time_received:
            pytest.skip("SNTP server did not respond (network may be unavailable)")
        if time_received:
            epoch_ms = time_received[0]
            # Should be an integer
            assert isinstance(epoch_ms, int)
            # Should be roughly current time (within last 10 years and next year)
            current_time_ms = int(time.time() * 1000)
            ten_years_ms = 10 * 365 * 24 * 60 * 60 * 1000
            assert epoch_ms > (current_time_ms - ten_years_ms)
            assert epoch_ms < (current_time_ms + 365 * 24 * 60 * 60 * 1000)
    finally:
        manager.close()


def test_sntp_multiple_requests():
    """Test multiple SNTP requests."""
    manager = Manager()
    time_received = []

    def handler(conn, ev, data):
        if ev == MG_EV_SNTP_TIME:
            time_received.append(data)

    try:
        conn = manager.sntp_connect("udp://time.google.com:123", handler=handler)
        manager.poll(10)

        # Send multiple requests
        conn.sntp_request()
        time.sleep(0.1)
        conn.sntp_request()
        time.sleep(0.1)
        conn.sntp_request()

        # Poll for responses
        for _ in range(200):
            manager.poll(50)
            if len(time_received) >= 3:
                break
            time.sleep(0.01)

        # SNTP requires UDP port 123 which may be blocked in CI
        if not time_received:
            pytest.skip("SNTP server did not respond (network may be unavailable)")
        assert len(time_received) >= 1
    finally:
        manager.close()


def test_sntp_method_exists():
    """Test that SNTP methods exist and are callable."""
    manager = Manager()

    try:
        # Manager should have sntp_connect
        assert hasattr(manager, "sntp_connect")

        conn = manager.sntp_connect("udp://time.google.com:123")
        manager.poll(10)

        # Connection should have sntp_request
        assert hasattr(conn, "sntp_request")

        # Should be callable without error
        conn.sntp_request()
        manager.poll(10)
    finally:
        manager.close()
