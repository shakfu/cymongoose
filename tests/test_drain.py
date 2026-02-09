"""Tests for connection draining (graceful close)."""

import time
import urllib.request

from cymongoose import MG_EV_CLOSE, MG_EV_HTTP_MSG

from .conftest import ServerThread


class TestDrain:
    """Test connection drain functionality."""

    def test_drain_closes_after_send(self):
        """Test that drain() closes connection after sending data."""
        close_count = [0]
        request_count = [0]

        def handler(conn, event, data):
            if event == MG_EV_HTTP_MSG:
                request_count[0] += 1
                conn.reply(200, b"Response sent")
                conn.drain()  # Should close after response is sent
            elif event == MG_EV_CLOSE:
                close_count[0] += 1

        with ServerThread(handler) as port:
            url = f"http://localhost:{port}/"

            # Make request
            response = urllib.request.urlopen(url, timeout=5)
            body = response.read().decode("utf-8")

            assert response.status == 200
            assert body == "Response sent"
            assert request_count[0] == 1

            # Give time for connection to close
            time.sleep(0.2)

            # Close event should have been triggered
            assert close_count[0] >= 1, "Connection should have closed after drain"

    def test_is_draining_property(self):
        """Test that is_draining property reflects drain state."""
        draining_state = []

        def handler(conn, event, data):
            if event == MG_EV_HTTP_MSG:
                # Check state before drain
                draining_state.append(("before", conn.is_draining))

                conn.reply(200, b"OK")
                conn.drain()

                # Check state after drain
                draining_state.append(("after", conn.is_draining))

        with ServerThread(handler) as port:
            url = f"http://localhost:{port}/"
            response = urllib.request.urlopen(url, timeout=5)
            response.read()

            time.sleep(0.1)

            # Verify drain state changed
            assert len(draining_state) == 2
            assert draining_state[0] == ("before", False)
            assert draining_state[1] == ("after", True)

    def test_multiple_requests_with_drain(self):
        """Test that drain works correctly for multiple sequential requests."""
        request_count = [0]

        def handler(conn, event, data):
            if event == MG_EV_HTTP_MSG:
                request_count[0] += 1
                conn.reply(200, f"Request #{request_count[0]}".encode())
                conn.drain()

        with ServerThread(handler) as port:
            url = f"http://localhost:{port}/"

            # Make multiple requests
            for i in range(3):
                response = urllib.request.urlopen(url, timeout=5)
                body = response.read().decode("utf-8")
                assert body == f"Request #{i + 1}"
                time.sleep(0.1)

            assert request_count[0] == 3

    def test_drain_vs_close(self):
        """Test difference between drain() and close()."""
        # This test documents the behavior difference
        # drain() = graceful close (flush buffers first)
        # close() = immediate close

        def handler(conn, event, data):
            if event == MG_EV_HTTP_MSG:
                conn.reply(200, b"Testing drain vs close")
                # Using drain here ensures response is sent
                conn.drain()

        with ServerThread(handler) as port:
            url = f"http://localhost:{port}/"
            response = urllib.request.urlopen(url, timeout=5)
            body = response.read()

            # Should receive full response
            assert body == b"Testing drain vs close"
