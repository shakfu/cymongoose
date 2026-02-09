#!/usr/bin/env python3
"""Example UDP echo server with client.

This example demonstrates:
1. UDP socket handling (connectionless protocol)
2. Server that echoes received datagrams back to sender
3. Client that sends datagrams and receives responses
4. Timer-based client sending
5. Custom protocol over UDP

Usage:
    python udp_echo_server.py [-l LISTEN_ADDR] [-c CONNECT_ADDR]

Example:
    python udp_echo_server.py -l udp://localhost:8765

Translation adapted from TCP echo tutorial with UDP patterns.

UDP is connectionless - no handshake, no guaranteed delivery, no ordering.
This makes it suitable for:
- Real-time applications (VoIP, gaming, video streaming)
- Small request/response protocols (DNS, SNTP)
- Broadcasting and multicasting

Key differences from TCP:
- No MG_EV_ACCEPT (server receives data directly)
- No MG_EV_CONNECT (client sends immediately)
- Each packet is independent (no stream)
- Need to handle packet loss and reordering in application layer
"""

import argparse
import signal

from cymongoose import (
    MG_EV_CLOSE,
    MG_EV_ERROR,
    MG_EV_OPEN,
    MG_EV_POLL,
    MG_EV_READ,
    Manager,
)

# Default configuration
DEFAULT_LISTEN = "udp://localhost:8765"
DEFAULT_CONNECT = "udp://localhost:8765"

# Global state
shutdown_requested = False
client_conn = None
client_counter = 0


def signal_handler(sig, frame):
    """Handle shutdown signals (Ctrl+C, SIGTERM)."""
    global shutdown_requested
    shutdown_requested = True


def server_handler(conn, ev, data):
    """UDP echo server event handler.

    Args:
        conn: Connection object
        ev: Event type
        data: Event data
    """
    if ev == MG_EV_OPEN and conn.is_listening:
        print(f"[SERVER {conn.id}] Listening on UDP...")

    elif ev == MG_EV_READ:
        # Echo received datagram back
        # In UDP, recv_data() returns the datagram without removing it
        # We need to call recv_data() to get it and it will be consumed
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
    """UDP client event handler.

    Args:
        conn: Connection object
        ev: Event type
        data: Event data
        config: Client configuration
    """
    global client_counter, client_conn

    if ev == MG_EV_OPEN:
        print(f"[CLIENT {conn.id}] UDP socket opened")
        client_counter = 1  # Start counter

    elif ev == MG_EV_READ:
        # Received echo response
        recv_data = conn.recv_data()
        if recv_data:
            print(f"[CLIENT {conn.id}] Received echo: {recv_data!r}")

    elif ev == MG_EV_CLOSE:
        print(f"[CLIENT {conn.id}] Socket closed")
        client_conn = None
        client_counter = 0

    elif ev == MG_EV_ERROR:
        error_msg = data if isinstance(data, str) else "Unknown error"
        print(f"[CLIENT {conn.id}] ERROR: {error_msg}")
        client_conn = None

    elif ev == MG_EV_POLL and client_counter > 0:
        # Send datagram after some poll cycles
        client_counter += 1

        if client_counter == 50:  # 50 x 100ms = 5s
            message = b"Hello, UDP echo server!"
            conn.send(message)
            print(f"[CLIENT {conn.id}] Sent: {message!r}")

        elif client_counter >= 100:  # Another 5s, then close
            print(f"[CLIENT {conn.id}] Closing socket...")
            conn.close()
            client_counter = 0


def timer_callback(manager, config):
    """Timer callback for client reconnection.

    Args:
        manager: Manager object
        config: Configuration dict
    """
    global client_conn

    if client_conn is None and config.get("run_client", False):
        # Create new UDP client connection
        print(f"\n[TIMER] Creating UDP client socket for {config['connect_addr']}...")
        try:
            # For UDP client, use connect() to set default destination
            client_conn = manager.connect(
                config["connect_addr"], handler=lambda c, e, d: client_handler(c, e, d, config)
            )
            print("[CLIENT] UDP socket created")
        except RuntimeError as e:
            print(f"[CLIENT] Failed to create socket: {e}")


def main():
    """Main function."""
    global shutdown_requested

    # Parse command-line arguments
    parser = argparse.ArgumentParser(description="UDP echo server and client")
    parser.add_argument(
        "-l", "--listen", default=DEFAULT_LISTEN, help=f"Listen address (default: {DEFAULT_LISTEN})"
    )
    parser.add_argument(
        "-c",
        "--connect",
        default=DEFAULT_CONNECT,
        help=f"Connect address for client (default: {DEFAULT_CONNECT})",
    )
    parser.add_argument("--client", action="store_true", help="Run client (sends to server)")
    parser.add_argument("--server", action="store_true", help="Run server (listens for datagrams)")

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
            print(f"UDP Echo Server started on {config['listen_addr']}")

        # Add timer for client (every 15s)
        if config["run_client"]:
            manager.timer_add(
                15000,  # 15 seconds
                repeat=True,
                run_now=True,  # Create socket immediately
                callback=lambda: timer_callback(manager, config),
            )
            print(f"UDP Client will send to {config['connect_addr']}")

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
