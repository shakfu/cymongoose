#!/usr/bin/env python3
"""cymongoose HTTP server for performance benchmarking."""

import signal
from cymongoose import Manager, MG_EV_HTTP_MSG

shutdown_requested = False


def signal_handler(sig, frame):
    """Handle shutdown signals."""
    global shutdown_requested
    shutdown_requested = True


def run_server(port: int = 8001):
    """Run cymongoose HTTP server."""
    global shutdown_requested

    # Register signal handlers
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    # Simple JSON response
    json_response = b'{"message":"Hello, World!"}'

    def handler(conn, ev, data):
        if ev == MG_EV_HTTP_MSG:
            conn.reply(200, json_response, headers={"Content-Type": "application/json"})

    manager = Manager(handler)
    manager.listen(f"http://0.0.0.0:{port}", http=True)
    print(f"cymongoose server listening on http://0.0.0.0:{port}", flush=True)

    # Run event loop
    try:
        while not shutdown_requested:
            manager.poll(100)
        print("\n Shutting down...")
    finally:
        manager.close()  # Clean up resources
        print("[x] Server stopped cleanly")


if __name__ == "__main__":
    import sys

    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8001
    run_server(port)
