#!/usr/bin/env python3
"""Example TCP echo server with client.

This example demonstrates:
1. Raw TCP socket handling (not HTTP)
2. Server that echoes received data back to client
3. Client that connects, sends data, and receives echo
4. Timer-based client reconnection
5. Custom protocol implementation

Usage:
    python tcp_echo_server.py [-l LISTEN_ADDR] [-c CONNECT_ADDR]

Example:
    python tcp_echo_server.py -l tcp://localhost:8765

Translation from C tutorial: thirdparty/mongoose/tutorials/tcp/tcp/main.c

This demonstrates raw TCP without HTTP layer - useful for custom protocols.
"""

import argparse
import signal

from cymongoose import (
    MG_EV_ACCEPT,
    MG_EV_CLOSE,
    MG_EV_CONNECT,
    MG_EV_ERROR,
    MG_EV_OPEN,
    MG_EV_POLL,
    MG_EV_READ,
    Manager,
)

# Default configuration
DEFAULT_LISTEN = "tcp://localhost:8765"
DEFAULT_CONNECT = "tcp://localhost:8765"

# Global state
shutdown_requested = False
client_conn = None
client_counter = 0


def signal_handler(sig, frame):
    """Handle shutdown signals (Ctrl+C, SIGTERM)."""
    global shutdown_requested
    shutdown_requested = True


def server_handler(conn, ev, data):
    """TCP echo server event handler.

    Args:
        conn: Connection object
        ev: Event type
        data: Event data
    """
    if ev == MG_EV_OPEN and conn.is_listening:
        print(f"[SERVER {conn.id}] Listening...")

    elif ev == MG_EV_ACCEPT:
        print(f"[SERVER {conn.id}] Accepted connection from {conn.remote_addr}")

    elif ev == MG_EV_READ:
        # Echo received data back
        recv_data = conn.recv_data()
        if recv_data:
            print(f"[SERVER {conn.id}] Received: {recv_data!r}")
            conn.send(recv_data)  # Echo back
            print(f"[SERVER {conn.id}] Echoed back")

    elif ev == MG_EV_CLOSE:
        print(f"[SERVER {conn.id}] Connection closed")

    elif ev == MG_EV_ERROR:
        error_msg = data if isinstance(data, str) else "Unknown error"
        print(f"[SERVER {conn.id}] ERROR: {error_msg}")


def client_handler(conn, ev, data, config):
    """TCP client event handler.

    Args:
        conn: Connection object
        ev: Event type
        data: Event data
        config: Client configuration
    """
    global client_counter, client_conn

    if ev == MG_EV_OPEN:
        print(f"[CLIENT {conn.id}] Initialized")

    elif ev == MG_EV_CONNECT:
        print(f"[CLIENT {conn.id}] Connected to {conn.remote_addr}")
        client_counter = 1  # Start counter for sending

    elif ev == MG_EV_READ:
        # Received echo response
        recv_data = conn.recv_data()
        if recv_data:
            print(f"[CLIENT {conn.id}] Received echo: {recv_data!r}")

    elif ev == MG_EV_CLOSE:
        print(f"[CLIENT {conn.id}] Disconnected")
        client_conn = None
        client_counter = 0

    elif ev == MG_EV_ERROR:
        error_msg = data if isinstance(data, str) else "Unknown error"
        print(f"[CLIENT {conn.id}] ERROR: {error_msg}")
        client_conn = None

    elif ev == MG_EV_POLL and client_counter > 0:
        # Send data after some poll cycles
        client_counter += 1

        if client_counter == 50:  # 50 x 100ms = 5s
            message = b"Hello, echo server!"
            conn.send(message)
            print(f"[CLIENT {conn.id}] Sent: {message!r}")

        elif client_counter >= 100:  # Another 5s, then close
            print(f"[CLIENT {conn.id}] Draining connection...")
            conn.drain()  # Graceful close
            client_counter = 0


def timer_callback(manager, config):
    """Timer callback for client reconnection.

    Args:
        manager: Manager object
        config: Configuration dict
    """
    global client_conn

    if client_conn is None and config.get("run_client", False):
        # Reconnect client
        print(f"\n[TIMER] Reconnecting client to {config['connect_addr']}...")
        try:
            client_conn = manager.connect(
                config["connect_addr"], handler=lambda c, e, d: client_handler(c, e, d, config)
            )
            print("[CLIENT] Connection initiated")
        except RuntimeError as e:
            print(f"[CLIENT] Failed to connect: {e}")


def main():
    """Main function."""
    global shutdown_requested

    # Parse command-line arguments
    parser = argparse.ArgumentParser(description="TCP echo server and client")
    parser.add_argument(
        "-l", "--listen", default=DEFAULT_LISTEN, help=f"Listen address (default: {DEFAULT_LISTEN})"
    )
    parser.add_argument(
        "-c",
        "--connect",
        default=DEFAULT_CONNECT,
        help=f"Connect address for client (default: {DEFAULT_CONNECT})",
    )
    parser.add_argument("--client", action="store_true", help="Run client (connects to server)")
    parser.add_argument(
        "--server", action="store_true", help="Run server (listens for connections)"
    )

    args = parser.parse_args()

    # If neither specified, run both
    if not args.client and not args.server:
        args.server = True
        args.client = True

    # Configuration
    config = {
        "listen_addr": args.listen,
        "connect_addr": args.connect,
        "run_client": args.client,
        "run_server": args.server,
    }

    # Register signal handlers
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    # Create manager
    manager = Manager()

    try:
        # Start server if requested
        if config["run_server"]:
            manager.listen(config["listen_addr"], handler=server_handler)
            print(f"TCP Echo Server started on {config['listen_addr']}")

        # Add timer for client reconnection (every 15s)
        if config["run_client"]:
            manager.timer_add(
                15000,  # 15 seconds
                repeat=True,
                run_now=True,  # Connect immediately
                callback=lambda: timer_callback(manager, config),
            )
            print(f"TCP Client will connect to {config['connect_addr']}")

        print("Press Ctrl+C to exit")
        print()

        # Event loop
        while not shutdown_requested:
            manager.poll(100)

        print("\nShutting down...")

    finally:
        manager.close()
        print("Stopped cleanly")


if __name__ == "__main__":
    main()
