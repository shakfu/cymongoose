#!/usr/bin/env python3
"""Example HTTP streaming client.

This example demonstrates:
1. Receiving large HTTP responses in chunks using MG_EV_READ
2. Processing response headers and body separately
3. Avoiding buffering entire response in memory
4. Handling both HTTP and HTTPS connections

Usage:
    python http_streaming_client.py [URL]

Example:
    python http_streaming_client.py http://info.cern.ch
    python http_streaming_client.py https://example.com

Translation from C tutorial: thirdparty/mongoose/tutorials/http/http-streaming-client/main.c

The default HTTP handler waits until the whole HTTP message is buffered.
This example shows how to receive a potentially large response in chunks
by handling MG_EV_READ events directly.
"""

import argparse
import signal
import sys

from cymongoose import (
    MG_EV_CLOSE,
    MG_EV_CONNECT,
    MG_EV_ERROR,
    MG_EV_READ,
    Manager,
)

# Default URL - the very first web page in history
DEFAULT_URL = "http://info.cern.ch"

# Global state
shutdown_requested = False


def signal_handler(sig, frame):
    """Handle shutdown signals (Ctrl+C, SIGTERM)."""
    global shutdown_requested
    shutdown_requested = True


def parse_url(url):
    """Parse URL into components.

    Returns:
        tuple: (scheme, host, port, uri)
    """
    # Simple URL parsing (url module not available in all contexts)
    if url.startswith("https://"):
        scheme = "https"
        rest = url[8:]
        default_port = 443
    elif url.startswith("http://"):
        scheme = "http"
        rest = url[7:]
        default_port = 80
    else:
        scheme = "http"
        rest = url
        default_port = 80

    # Split host and path
    if "/" in rest:
        host_port, uri = rest.split("/", 1)
        uri = "/" + uri
    else:
        host_port = rest
        uri = "/"

    # Split host and port
    if ":" in host_port:
        host, port_str = host_port.rsplit(":", 1)
        try:
            port = int(port_str)
        except ValueError:
            port = default_port
    else:
        host = host_port
        port = default_port

    return scheme, host, port, uri


def streaming_handler(conn, ev, data, config):
    """HTTP streaming event handler.

    Args:
        conn: Connection object
        ev: Event type
        data: Event data
        config: Client configuration dict
    """
    if ev == MG_EV_CONNECT:
        # Connected to server
        scheme, host, port, uri = config["url_parts"]

        # Send HTTP request manually
        request = f"GET {uri} HTTP/1.1\r\nConnection: close\r\nHost: {host}\r\n\r\n"
        conn.send(request.encode("utf-8"))

        print(f"Connected to {host}:{port}", file=sys.stderr)
        print(f"Sending request for {uri}", file=sys.stderr)

    elif ev == MG_EV_READ:
        # Data received - stream it to stdout
        # This is the key difference from normal HTTP handling:
        # we process data as it arrives instead of waiting for the full response

        if not config.get("headers_parsed", False):
            # First read - parse headers
            recv_data = conn.recv_data()

            # Look for end of headers (\r\n\r\n)
            header_end = recv_data.find(b"\r\n\r\n")
            if header_end >= 0:
                # Found end of headers
                header_end += 4

                # Print headers to stderr
                headers = recv_data[:header_end].decode("utf-8", errors="ignore")
                print("Response headers:", file=sys.stderr)
                print(headers, file=sys.stderr)

                # Print body to stdout
                body_start = recv_data[header_end:]
                if body_start:
                    sys.stdout.buffer.write(body_start)
                    sys.stdout.buffer.flush()

                # Mark headers as parsed
                config["headers_parsed"] = True
            # If headers not complete yet, wait for more data
        else:
            # Headers already parsed, stream body to stdout
            recv_data = conn.recv_data()
            if recv_data:
                sys.stdout.buffer.write(recv_data)
                sys.stdout.buffer.flush()

    elif ev == MG_EV_CLOSE:
        # Connection closed
        print("\nConnection closed", file=sys.stderr)
        config["done"] = True

    elif ev == MG_EV_ERROR:
        # Error occurred
        error_msg = data if isinstance(data, str) else "Unknown error"
        print(f"\nError: {error_msg}", file=sys.stderr)
        config["done"] = True


def main():
    """Main function."""
    global shutdown_requested

    # Parse command-line arguments
    parser = argparse.ArgumentParser(description="HTTP streaming client example")
    parser.add_argument(
        "url", nargs="?", default=DEFAULT_URL, help=f"URL to fetch (default: {DEFAULT_URL})"
    )

    args = parser.parse_args()

    # Parse URL
    url_parts = parse_url(args.url)
    scheme, host, port, uri = url_parts

    # Configuration
    config = {
        "url": args.url,
        "url_parts": url_parts,
        "headers_parsed": False,
        "done": False,
    }

    # Register signal handlers
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    # Create manager
    manager = Manager()

    try:
        # Connect to server
        connect_url = f"{scheme}://{host}:{port}"
        print(f"Connecting to {connect_url}...", file=sys.stderr)

        manager.connect(connect_url, handler=lambda c, e, d: streaming_handler(c, e, d, config))

        # Event loop
        while not shutdown_requested and not config["done"]:
            manager.poll(100)

        if shutdown_requested:
            print("\nInterrupted by user", file=sys.stderr)

    finally:
        manager.close()


if __name__ == "__main__":
    main()
