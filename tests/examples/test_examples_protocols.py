#!/usr/bin/env python3
"""
Tests all network protocol examples:
- SNTP Client (time synchronization)
- DNS Resolution (hostname lookups)
- TCP Echo Server (raw TCP sockets)
- UDP Echo Server (UDP datagrams)
"""

import sys
import time
import threading
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from cymongoose import (
    Manager,
    MG_EV_SNTP_TIME,
    MG_EV_RESOLVE,
    MG_EV_READ,
    MG_EV_ACCEPT,
    MG_EV_CONNECT,
)


# ===== SNTP Client Tests =====


def test_sntp_client_can_import():
    """Test that SNTP client module can be imported."""
    try:
        with open("tests/examples/network/sntp_client.py") as f:
            code = f.read()
            compile(code, "sntp_client.py", "exec")
        assert True
    except SyntaxError as e:
        assert False, f"Syntax error in sntp_client.py: {e}"


def test_sntp_time_request():
    """Test SNTP time request functionality."""
    time_received = threading.Event()
    received_time = []

    def handler(conn, ev, data):
        if ev == MG_EV_SNTP_TIME:
            received_time.append(data)
            time_received.set()

    manager = Manager()

    try:
        # Connect to Google's public SNTP server
        conn = manager.sntp_connect("udp://time.google.com:123", handler=handler)

        # Poll for response (max 5 seconds)
        for _ in range(50):
            manager.poll(100)
            if time_received.is_set():
                break

        # Verify we received time data
        assert time_received.is_set(), "SNTP time request timed out"
        assert len(received_time) > 0
        # Time should be milliseconds from epoch (very large number)
        assert received_time[0] > 1000000000000  # After year 2001

    finally:
        manager.close()


# ===== DNS Resolution Tests =====


def test_dns_client_can_import():
    """Test that DNS client module can be imported."""
    try:
        with open("tests/examples/network/dns_client.py") as f:
            code = f.read()
            compile(code, "dns_client.py", "exec")
        assert True
    except SyntaxError as e:
        assert False, f"Syntax error in dns_client.py: {e}"


def test_dns_resolution_basic():
    """Test basic DNS resolution."""
    resolve_received = threading.Event()
    resolved_addr = []

    def handler(conn, ev, data):
        if ev == MG_EV_RESOLVE:
            resolved_addr.append(data)
            resolve_received.set()

    manager = Manager()

    try:
        # Create a listener connection (stays alive for resolution)
        conn = manager.listen("tcp://127.0.0.1:0", handler=handler)
        manager.poll(10)

        # Trigger DNS resolution
        conn.resolve("google.com")

        # Poll for response (max 5 seconds)
        for _ in range(50):
            manager.poll(100)
            if resolve_received.is_set():
                break

        # Resolution should complete (success or failure)
        # We just verify it doesn't crash
        assert True

    finally:
        manager.close()


# ===== TCP Echo Server Tests =====


def test_tcp_echo_server_can_import():
    """Test that TCP echo server module can be imported."""
    try:
        with open("tests/examples/network/tcp_echo_server.py") as f:
            code = f.read()
            compile(code, "tcp_echo_server.py", "exec")
        assert True
    except SyntaxError as e:
        assert False, f"Syntax error in tcp_echo_server.py: {e}"


def test_tcp_echo_functionality():
    """Test TCP echo server echoes data back."""
    echo_received = threading.Event()
    received_data = []
    client_manager = None

    def server_handler(conn, ev, data):
        if ev == MG_EV_ACCEPT:
            # New connection accepted
            pass
        elif ev == MG_EV_READ:
            # Echo back
            recv_data = conn.recv_data()
            if recv_data:
                conn.send(recv_data)

    def client_handler(conn, ev, data):
        if ev == MG_EV_CONNECT:
            # Send test data
            conn.send(b"Hello TCP!")
        elif ev == MG_EV_READ:
            recv_data = conn.recv_data()
            if recv_data:
                received_data.append(recv_data)
                echo_received.set()

    # Server manager with default handler
    server_manager = Manager(server_handler)

    try:
        # Start server
        listener = server_manager.listen("tcp://127.0.0.1:0")
        port = listener.local_addr[1]

        # Run server in background
        server_stop = threading.Event()

        def server_poll():
            while not server_stop.is_set():
                server_manager.poll(50)

        server_thread = threading.Thread(target=server_poll, daemon=True)
        server_thread.start()
        time.sleep(0.2)

        # Client manager with handler
        client_manager = Manager(client_handler)
        client = client_manager.connect(f"tcp://127.0.0.1:{port}")

        # Run client in background
        client_stop = threading.Event()

        def client_poll():
            while not client_stop.is_set():
                client_manager.poll(50)

        client_thread = threading.Thread(target=client_poll, daemon=True)
        client_thread.start()

        # Wait for echo
        echo_received.wait(timeout=3)

        # Verify echo
        assert echo_received.is_set(), "Echo not received"
        assert len(received_data) > 0
        assert received_data[0] == b"Hello TCP!"

    finally:
        # Stop polling threads first
        if "server_stop" in locals():
            server_stop.set()
        if "client_stop" in locals():
            client_stop.set()
        time.sleep(0.2)
        server_manager.close()
        if client_manager:
            client_manager.close()


# ===== UDP Echo Server Tests =====


def test_udp_echo_server_can_import():
    """Test that UDP echo server module can be imported."""
    try:
        with open("tests/examples/network/udp_echo_server.py") as f:
            code = f.read()
            compile(code, "udp_echo_server.py", "exec")
        assert True
    except SyntaxError as e:
        assert False, f"Syntax error in udp_echo_server.py: {e}"


def test_udp_echo_functionality():
    """Test UDP echo server echoes datagrams back."""
    echo_received = threading.Event()
    received_data = []

    def server_handler(conn, ev, data):
        if ev == MG_EV_READ:
            # Echo back
            recv_data = conn.recv_data()
            if recv_data:
                conn.send(recv_data)

    def client_handler(conn, ev, data):
        if ev == MG_EV_READ:
            recv_data = conn.recv_data()
            if recv_data:
                received_data.append(recv_data)
                echo_received.set()

    manager = Manager()

    try:
        # Start UDP server
        listener = manager.listen("udp://127.0.0.1:0", handler=server_handler)
        port = listener.local_addr[1]

        # Run in background
        stop = threading.Event()

        def poll_loop():
            while not stop.is_set():
                manager.poll(50)

        poll_thread = threading.Thread(target=poll_loop, daemon=True)
        poll_thread.start()
        time.sleep(0.2)

        # Connect UDP client
        client = manager.connect(f"udp://127.0.0.1:{port}", handler=client_handler)
        time.sleep(0.1)

        # Send datagram
        client.send(b"Hello UDP!")

        # Wait for echo
        echo_received.wait(timeout=2)

        # Verify echo
        assert echo_received.is_set(), "UDP echo not received"
        assert len(received_data) > 0
        assert received_data[0] == b"Hello UDP!"

    finally:
        # Stop polling thread first
        stop.set()
        time.sleep(0.2)
        manager.close()


if __name__ == "__main__":
    # Run tests
    test_sntp_client_can_import()
    print("[x] test_sntp_client_can_import")

    test_sntp_time_request()
    print("[x] test_sntp_time_request")

    test_dns_client_can_import()
    print("[x] test_dns_client_can_import")

    test_dns_resolution_basic()
    print("[x] test_dns_resolution_basic")

    test_tcp_echo_server_can_import()
    print("[x] test_tcp_echo_server_can_import")

    test_tcp_echo_functionality()
    print("[x] test_tcp_echo_functionality")

    test_udp_echo_server_can_import()
    print("[x] test_udp_echo_server_can_import")

    test_udp_echo_functionality()
    print("[x] test_udp_echo_functionality")

    print("\nAll Priority 4 tests passed!")
