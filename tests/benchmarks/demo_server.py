#!/usr/bin/env python3
"""
Demo cymongoose HTTP server.

Run this and visit http://localhost:8765/ in your browser or use curl.
Press Ctrl+C to stop.
"""

import signal
from cymongoose import Manager, MG_EV_HTTP_MSG

shutdown_requested = False


def signal_handler(sig, frame):
    """Handle shutdown signals (Ctrl+C, SIGTERM)."""
    global shutdown_requested
    shutdown_requested = True


def handler(conn, ev, data):
    """Handle HTTP requests."""
    if ev == MG_EV_HTTP_MSG:
        # Log the request
        print(f"{data.method} {data.uri}")

        # Send JSON response
        conn.reply(
            200,
            b'{"message":"Hello from cymongoose!","server":"C-based event loop"}',
            headers={"Content-Type": "application/json"},
        )


def main():
    global shutdown_requested

    # Register signal handlers for graceful shutdown
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    port = 8765
    manager = Manager(handler)
    manager.listen(f"http://0.0.0.0:{port}", http=True)

    print(f" cymongoose HTTP server running on http://localhost:{port}/")
    print(f"   Press Ctrl+C to stop")
    print(f"   USE_NOGIL optimization enabled")
    print()

    try:
        while not shutdown_requested:
            manager.poll(100)
        print("\n Shutting down...")
    finally:
        manager.close()  # Clean up resources
        print("[x] Server stopped cleanly")


if __name__ == "__main__":
    main()
