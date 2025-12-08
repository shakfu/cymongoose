#!/usr/bin/env python3
"""Simple standalone benchmark for cymongoose HTTP server."""

import subprocess
import sys
import time
import threading
import socket


def get_free_port():
    """Get a free TCP port."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.bind(("", 0))
    port = sock.getsockname()[1]
    sock.close()
    return port


def main():
    """Run a simple benchmark."""
    # Start server in this process using threading
    print("Starting cymongoose server...")

    from cymongoose import Manager, MG_EV_HTTP_MSG

    port = get_free_port()
    json_response = b'{"message":"Hello, World!"}'
    stop_flag = threading.Event()

    def handler(conn, ev, data):
        if ev == MG_EV_HTTP_MSG:
            conn.reply(200, json_response, headers={"Content-Type": "application/json"})

    ready_flag = threading.Event()

    def run_server():
        manager = Manager(handler)  # Pass handler to Manager, not listen()
        manager.listen(f"http://0.0.0.0:{port}", http=True)
        print(f"Server listening on http://0.0.0.0:{port}", flush=True)
        ready_flag.set()
        while not stop_flag.is_set():
            manager.poll(100)

    server_thread = threading.Thread(target=run_server, daemon=True)
    server_thread.start()

    # Wait for server to be ready
    if not ready_flag.wait(timeout=5):
        print("ERROR: Server failed to start")
        sys.exit(1)

    time.sleep(1)  # Give server extra time to accept connections

    print(f"Server started on port {port}!\n")

    # Test with curl
    print("Testing with curl...")
    result = subprocess.run(
        ["curl", "-s", f"http://localhost:{port}/"], capture_output=True, text=True, timeout=5
    )
    print(f"Response: {result.stdout}")

    # Run benchmark with ab (lower concurrency for macOS compatibility)
    print("\nRunning benchmark (10,000 requests, 10 concurrent)...\n")
    result = subprocess.run(
        ["ab", "-n", "10000", "-c", "10", "-q", f"http://localhost:{port}/"],
        capture_output=True,
        text=True,
    )

    # Parse results
    if result.returncode != 0:
        print(f"ERROR: ab failed with return code {result.returncode}")
        print(f"stdout: {result.stdout[:500]}")
        print(f"stderr: {result.stderr[:500]}")
    else:
        for line in result.stdout.split("\n"):
            if any(
                keyword in line
                for keyword in [
                    "Requests per second",
                    "Time per request",
                    "Failed requests",
                    "Transfer rate",
                ]
            ):
                print(line)

    # Cleanup
    print("\nStopping server...")
    stop_flag.set()
    time.sleep(0.2)


if __name__ == "__main__":
    main()
