#!/usr/bin/env python3
"""Example multi-threaded HTTP server with background work offloading.

This example demonstrates:
1. Offloading long-running work to background threads
2. Using Manager.wakeup() to send results back to event loop
3. Non-blocking request handling with threading
4. Performance comparison: single-threaded vs multi-threaded
5. Thread-safe patterns with connection IDs

Usage:
    python multithreaded_server.py [-l LISTEN_URL] [-t SLEEP_TIME]

Example:
    python multithreaded_server.py -l http://0.0.0.0:8000 -t 2

    # Test endpoints:
    curl http://localhost:8000/fast    # Single-threaded, immediate response
    curl http://localhost:8000/slow    # Multi-threaded, 2-second delay

Translation from C tutorial: thirdparty/mongoose/tutorials/core/multi-threaded/main.c

Multi-threading Pattern:
1. HTTP request arrives -> handler receives MG_EV_HTTP_MSG
2. Spawn background thread with connection ID and request data
3. Thread does expensive work (database query, external API, computation)
4. Thread calls manager.wakeup(conn_id, result_data)
5. Main event loop receives MG_EV_WAKEUP
6. Handler sends HTTP response with thread result

Benefits:
- Main event loop stays responsive
- Multiple requests processed concurrently
- CPU-intensive or I/O-bound work doesn't block other clients
- Simple thread pool pattern (can be extended)

Important Notes:
- Connection objects cannot be safely accessed from threads
- Use connection ID (integer) to identify connections
- Only use wakeup() to communicate with main thread
- Manager.wakeup() is the only thread-safe method
"""

import argparse
import signal
import threading
import time

from cymongoose import (
    MG_EV_HTTP_MSG,
    MG_EV_WAKEUP,
    Manager,
)

# Default configuration
DEFAULT_LISTEN = "http://0.0.0.0:8000"
DEFAULT_SLEEP = 2  # seconds

# Global state
shutdown_requested = False
request_counter = 0
thread_counter = 0


def signal_handler(sig, frame):
    """Handle shutdown signals (Ctrl+C, SIGTERM)."""
    global shutdown_requested
    shutdown_requested = True


def worker_thread(manager, conn_id, request_uri, sleep_time):
    """Background worker thread that simulates expensive work.

    Args:
        manager: Manager object (for wakeup only)
        conn_id: Connection ID to send result to
        request_uri: Original request URI
        sleep_time: How long to sleep (simulate work)
    """
    global thread_counter
    thread_id = thread_counter
    thread_counter += 1

    print(f"  [THREAD {thread_id}] Started for connection {conn_id}")
    print(f"  [THREAD {thread_id}] Processing request: {request_uri}")
    print(f"  [THREAD {thread_id}] Simulating {sleep_time}s of work...")

    # Simulate expensive work (database query, external API call, computation, etc.)
    time.sleep(sleep_time)

    # Prepare result (must be bytes)
    result = f"Thread {thread_id} completed after {sleep_time}s".encode("utf-8")

    print(f"  [THREAD {thread_id}] Work done, sending result back")

    # Send result back to main event loop
    # IMPORTANT: This is the ONLY thread-safe way to communicate with connections
    # IMPORTANT: Data must be bytes, not str
    try:
        manager.wakeup(conn_id, result)
    except RuntimeError as e:
        # Connection may have closed while we were working
        print(f"  [THREAD {thread_id}] Failed to wakeup: {e}")


def http_handler(conn, ev, data, config):
    """HTTP event handler.

    Args:
        conn: Connection object
        ev: Event type
        data: Event data
        config: Server configuration
    """
    global request_counter

    if ev == MG_EV_HTTP_MSG:
        hm = data  # HttpMessage object
        request_counter += 1
        req_num = request_counter

        print(f"\n[REQ {req_num}] {hm.method} {hm.uri} from connection {conn.id}")

        if hm.uri == "/fast":
            # Single-threaded fast path
            # Responds immediately without spawning thread
            html = f"""<!DOCTYPE html>
<html>
<head><title>Fast Response</title></head>
<body>
    <h1>Fast Response (Single-threaded)</h1>
    <p>Request #{req_num} processed immediately</p>
    <p>This endpoint responds without spawning a thread.</p>
    <p><a href="/slow">Try slow endpoint</a></p>
</body>
</html>
"""
            conn.reply(200, html, headers={"Content-Type": "text/html"})
            conn.drain()
            print(f"[REQ {req_num}] Fast response sent immediately")

        elif hm.uri == "/slow":
            # Multi-threaded slow path
            # Spawn thread to handle expensive work
            print(f"[REQ {req_num}] Spawning worker thread...")

            # Start background thread
            # IMPORTANT: Pass connection ID, not connection object!
            thread = threading.Thread(
                target=worker_thread,
                args=(config["manager"], conn.id, hm.uri, config["sleep_time"]),
                daemon=True,
            )
            thread.start()

            # Handler returns immediately without sending response
            # Response will be sent when MG_EV_WAKEUP is received

        elif hm.uri == "/":
            # Homepage
            html = """<!DOCTYPE html>
<html>
<head>
    <title>Multi-threaded Server</title>
    <style>
        body { font-family: Arial, sans-serif; margin: 40px; }
        .endpoint { background: #f0f0f0; padding: 10px; margin: 10px 0; border-radius: 5px; }
        code { background: #e0e0e0; padding: 2px 5px; border-radius: 3px; }
    </style>
</head>
<body>
    <h1>Multi-threaded HTTP Server</h1>
    <p>This server demonstrates background work offloading with threads.</p>

    <h2>Available Endpoints:</h2>

    <div class="endpoint">
        <h3><code>GET /fast</code></h3>
        <p>Single-threaded path - responds immediately</p>
        <p><a href="/fast">Try it</a></p>
    </div>

    <div class="endpoint">
        <h3><code>GET /slow</code></h3>
        <p>Multi-threaded path - spawns worker thread with 2s delay</p>
        <p><a href="/slow">Try it</a> (takes 2 seconds)</p>
    </div>

    <h2>Test Concurrency:</h2>
    <p>Open multiple tabs and request <code>/slow</code> simultaneously
    to see concurrent processing.</p>
    <pre>
# In terminal:
curl http://localhost:8000/fast     # Immediate
curl http://localhost:8000/slow &   # Background
curl http://localhost:8000/slow &   # Background
curl http://localhost:8000/slow &   # Background
wait                                # All finish ~2s
    </pre>
</body>
</html>
"""
            conn.reply(200, html, headers={"Content-Type": "text/html"})
            conn.drain()

        else:
            conn.reply(404, "Not Found")
            conn.drain()

    elif ev == MG_EV_WAKEUP:
        # Received result from worker thread
        # data is bytes, decode to string
        result_message = data.decode("utf-8") if isinstance(data, bytes) else data

        print(f"[CONN {conn.id}] Received wakeup: {result_message}")

        html = f"""<!DOCTYPE html>
<html>
<head><title>Slow Response</title></head>
<body>
    <h1>Slow Response (Multi-threaded)</h1>
    <p>Worker thread result: <strong>{result_message}</strong></p>
    <p>The main event loop stayed responsive while this was processing!</p>
    <p><a href="/">Back to home</a> | <a href="/slow">Try again</a></p>
</body>
</html>
"""
        conn.reply(200, html, headers={"Content-Type": "text/html"})
        conn.drain()


def main():
    """Main function."""
    global shutdown_requested

    # Parse command-line arguments
    parser = argparse.ArgumentParser(description="Multi-threaded HTTP server")
    parser.add_argument(
        "-l", "--listen", default=DEFAULT_LISTEN, help=f"Listen URL (default: {DEFAULT_LISTEN})"
    )
    parser.add_argument(
        "-t",
        "--sleep-time",
        type=float,
        default=DEFAULT_SLEEP,
        help=f"Worker thread sleep time in seconds (default: {DEFAULT_SLEEP})",
    )

    args = parser.parse_args()

    config = {
        "listen": args.listen,
        "sleep_time": args.sleep_time,
        "manager": None,  # Will be set after manager creation
    }

    # Register signal handlers
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    # Create manager with wakeup support enabled
    # IMPORTANT: enable_wakeup=True is required for Manager.wakeup() to work
    manager = Manager(lambda c, e, d: http_handler(c, e, d, config), enable_wakeup=True)
    config["manager"] = manager

    try:
        # Start HTTP server
        manager.listen(args.listen, http=True)
        print(f"Multi-threaded Server started on {args.listen}")
        print(f"Worker thread sleep time: {args.sleep_time}s")
        print("Press Ctrl+C to exit")
        print()
        print("Test endpoints:")
        print("  curl http://localhost:8000/")
        print("  curl http://localhost:8000/fast")
        print("  curl http://localhost:8000/slow")
        print()

        # Event loop
        while not shutdown_requested:
            manager.poll(100)

        print("\nShutting down...")

    finally:
        manager.close()
        print("Server stopped cleanly")


if __name__ == "__main__":
    main()
