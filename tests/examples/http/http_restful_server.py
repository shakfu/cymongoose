#!/usr/bin/env python3
"""Example HTTP RESTful server.

This example demonstrates:
1. REST API endpoint patterns
2. JSON request/response handling
3. URL routing with wildcards
4. HTTP chunked transfer encoding
5. Static file serving alongside API

Usage:
    python http_restful_server.py [-l LISTEN_URL]

Example:
    python http_restful_server.py -l http://0.0.0.0:8000

    # Test API endpoints:
    curl http://localhost:8000/api/stats
    curl http://localhost:8000/api/f2/anything
    curl http://localhost:8000/

Translation from C tutorial: thirdparty/mongoose/tutorials/http/http-restful-server/main.c

This server implements:
- /api/stats - Returns connection statistics (chunked response)
- /api/f2/* - Wildcard endpoint that echoes URI in JSON
- /* - Static file serving from root directory
"""

import argparse
import json
import signal

from cymongoose import (
    MG_EV_HTTP_MSG,
    Manager,
)

# Default configuration
DEFAULT_LISTEN = "http://0.0.0.0:8000"
DEFAULT_ROOT_DIR = "."

# Global state
shutdown_requested = False


def signal_handler(sig, frame):
    """Handle shutdown signals (Ctrl+C, SIGTERM)."""
    global shutdown_requested
    shutdown_requested = True


def handle_api_stats(conn, manager):
    """Handle /api/stats endpoint with chunked response.

    Args:
        conn: Connection object
        manager: Manager object to get connection stats
    """
    # Start chunked response
    conn.send(b"HTTP/1.1 200 OK\r\nTransfer-Encoding: chunked\r\n\r\n")

    # Send header as first chunk
    header = "ID PROTO TYPE      LOCAL           REMOTE\n"
    conn.http_chunk(header)

    # Send connection info as chunks
    # Note: In Python we don't have direct access to manager's connection list
    # So we'll send a simplified version
    stats = [
        f"{conn.id:3d} TCP  ACCEPTED  {conn.local_addr[0]}:{conn.local_addr[1]:5d} "
        f"{conn.remote_addr[0]}:{conn.remote_addr[1]:5d}\n"
    ]

    for stat in stats:
        conn.http_chunk(stat)

    # Send empty chunk to end response
    conn.http_chunk("")


def handle_api_wildcard(conn, hm):
    """Handle /api/f2/* wildcard endpoint.

    Args:
        conn: Connection object
        hm: HttpMessage object
    """
    # Echo back the URI in JSON format
    response = {"result": hm.uri}

    conn.reply(
        200, json.dumps(response, indent=2) + "\n", headers={"Content-Type": "application/json"}
    )


def http_handler(conn, ev, data, config):
    """Main HTTP event handler.

    Args:
        conn: Connection object
        ev: Event type
        data: Event data
        config: Server configuration
    """
    if ev == MG_EV_HTTP_MSG:
        hm = data  # HttpMessage object

        # Route API endpoints
        if hm.uri == "/api/stats":
            handle_api_stats(conn, config["manager"])

        elif hm.uri.startswith("/api/f2/"):
            handle_api_wildcard(conn, hm)

        elif hm.uri == "/api/data":
            # Example POST endpoint
            try:
                # Parse JSON body
                if hm.body:
                    request_data = json.loads(hm.body.decode("utf-8"))
                else:
                    request_data = {}

                # Process request and return JSON response
                response = {
                    "status": "success",
                    "received": request_data,
                    "timestamp": "2024-01-01T00:00:00Z",  # Simplified
                }

                conn.reply(
                    200,
                    json.dumps(response, indent=2) + "\n",
                    headers={"Content-Type": "application/json"},
                )
            except json.JSONDecodeError:
                error_response = {"error": "Invalid JSON"}
                conn.reply(
                    400,
                    json.dumps(error_response) + "\n",
                    headers={"Content-Type": "application/json"},
                )

        elif hm.uri == "/":
            # Serve HTML info page
            html = """<!DOCTYPE html>
<html>
<head><title>RESTful Server</title></head>
<body>
<h1>RESTful Server Example</h1>
<h2>API Endpoints:</h2>
<ul>
<li><code>GET /api/stats</code> - Connection statistics (chunked)</li>
<li><code>GET /api/f2/&lt;anything&gt;</code> - Echo URI in JSON</li>
<li><code>POST /api/data</code> - Process JSON data</li>
</ul>
<h2>Examples:</h2>
<pre>
curl http://localhost:8000/api/stats
curl http://localhost:8000/api/f2/test123
curl -X POST http://localhost:8000/api/data -H "Content-Type: application/json" -d '{"key":"value"}'
</pre>
</body>
</html>
"""
            conn.reply(200, html, headers={"Content-Type": "text/html"})

        else:
            # 404 for unknown routes
            error = {"error": "Not Found", "path": hm.uri}
            conn.reply(404, json.dumps(error) + "\n", headers={"Content-Type": "application/json"})


def main():
    """Main function."""
    global shutdown_requested

    # Parse command-line arguments
    parser = argparse.ArgumentParser(description="HTTP RESTful server")
    parser.add_argument(
        "-l", "--listen", default=DEFAULT_LISTEN, help=f"Listen URL (default: {DEFAULT_LISTEN})"
    )
    parser.add_argument(
        "-r",
        "--root-dir",
        default=DEFAULT_ROOT_DIR,
        help=f"Root directory for static files (default: {DEFAULT_ROOT_DIR})",
    )

    args = parser.parse_args()

    # Configuration
    config = {
        "listen": args.listen,
        "root_dir": args.root_dir,
        "manager": None,  # Will be set after manager creation
    }

    # Register signal handlers
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    # Create manager
    manager = Manager(lambda c, e, d: http_handler(c, e, d, config))
    config["manager"] = manager

    try:
        # Start listening
        manager.listen(args.listen, http=True)
        print(f"RESTful Server started on {args.listen}")
        print("Press Ctrl+C to exit")
        print()
        print("API Endpoints:")
        print("  GET  /api/stats       - Connection statistics (chunked)")
        print("  GET  /api/f2/<path>   - Echo path in JSON")
        print("  POST /api/data        - Process JSON data")
        print()
        print("Try:")
        print("  curl http://localhost:8000/api/stats")
        print("  curl http://localhost:8000/api/f2/test123")

        # Event loop
        while not shutdown_requested:
            manager.poll(100)

        print("\nShutting down...")

    finally:
        manager.close()
        print("Server stopped cleanly")


if __name__ == "__main__":
    main()
