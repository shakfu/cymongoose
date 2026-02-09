#!/usr/bin/env python3
"""
Graceful shutdown via signal handlers with conn.drain()
Run: python drain_experiment_signal.py
Stop: Ctrl+C or kill -TERM <pid>
"""

import signal

from cymongoose import MG_EV_CLOSE, MG_EV_HTTP_MSG, MG_EV_POLL, Manager

# Shutdown flag and connection tracking
shutdown_requested = False
active_connections = {}  # id -> Connection mapping


def signal_handler(sig, frame):
    """Handle shutdown signals (Ctrl+C, SIGTERM)."""
    global shutdown_requested
    print(f"\nReceived signal {sig}, initiating graceful shutdown...")
    shutdown_requested = True


def handler(conn, ev, data):
    """HTTP request handler with connection tracking and draining."""
    global active_connections

    if ev == MG_EV_HTTP_MSG:
        # Track this connection
        active_connections[conn.id] = conn

        # Send response
        conn.reply(200, b'{"message": "Hello World", "shutdown": "graceful"}')

        # Drain instead of close to ensure response is sent
        conn.drain()

    elif ev == MG_EV_POLL:
        # If shutdown requested and this connection hasn't been drained yet, drain it
        if shutdown_requested and conn.id in active_connections and not conn.is_draining:
            print(f"Draining connection {conn.id} during shutdown")
            conn.drain()

    elif ev == MG_EV_CLOSE:
        # Remove from tracking when connection closes
        active_connections.pop(conn.id, None)


def main():
    global shutdown_requested, active_connections

    # Register signal handlers
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    manager = Manager(handler)
    manager.listen("http://0.0.0.0:8000", http=True)

    print("Server running on http://0.0.0.0:8000")
    print("Press Ctrl+C or send SIGTERM to shutdown gracefully...")

    try:
        # Main event loop
        while not shutdown_requested:
            manager.poll(100)  # 100ms for responsive shutdown

        # Shutdown initiated - drain all active connections
        print(f"\nDraining {len(active_connections)} active connections...")

        # Continue polling to let connections drain
        max_drain_time_ms = 5000  # 5 seconds max
        drain_cycles = 0
        max_drain_cycles = max_drain_time_ms // 100

        while active_connections and drain_cycles < max_drain_cycles:
            manager.poll(100)
            drain_cycles += 1

            if drain_cycles % 10 == 0:  # Print every second
                print(f"Still draining... {len(active_connections)} connections remaining")

        if active_connections:
            print(f"Warning: {len(active_connections)} connections did not drain in time")
            print("Forcing shutdown...")
        else:
            print("All connections drained successfully")

    finally:
        manager.close()
        print("Server stopped cleanly")


if __name__ == "__main__":
    main()
