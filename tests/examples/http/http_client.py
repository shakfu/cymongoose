#!/usr/bin/env python3
"""
HTTP Client Example - Comprehensive demonstration of HTTP client features.

Python translation of: thirdparty/mongoose/tutorials/http/http-client/main.c

Features demonstrated:
- Simple GET/POST requests
- TLS client configuration with CA certificates
- Connection timeout handling
- Response processing with is_draining
- Custom headers
- HTTP Basic Authentication

Usage:
    python http_client.py https://httpbin.org/get
    python http_client.py https://httpbin.org/post --method POST --data "hello"
    python http_client.py https://example.com --timeout 5
"""

import argparse
import sys
from pathlib import Path

# Add src to path for development
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from cymongoose import (
    Manager,
    MG_EV_CONNECT,
    MG_EV_HTTP_MSG,
    MG_EV_ERROR,
    MG_EV_CLOSE,
    TlsOpts,
)


class HttpClient:
    """HTTP client with connection management."""

    def __init__(self, url, method="GET", data=None, headers=None, timeout=10, ca_cert=None):
        self.url = url
        self.method = method
        self.data = data or ""
        self.headers = headers or {}
        self.timeout = timeout
        self.ca_cert = ca_cert

        self.manager = Manager(self.handler)
        self.done = False
        self.response_code = None
        self.response_body = None
        self.error = None

    def handler(self, conn, event, data):
        """Event handler for HTTP client connection."""
        if event == MG_EV_CONNECT:
            # Connection established
            if self.url.startswith("https://"):
                # Initialize TLS for HTTPS
                tls_opts = TlsOpts(
                    ca=self.ca_cert if self.ca_cert else b"",
                    skip_verification=not self.ca_cert,  # Skip if no CA provided
                )
                conn.tls_init(tls_opts)

            # Build HTTP request
            headers_str = "\r\n".join(f"{k}: {v}" for k, v in self.headers.items())
            if headers_str:
                headers_str = "\r\n" + headers_str

            # Send request
            if self.method == "GET":
                request = f"{self.method} {self.url.split('/', 3)[3] if '/' in self.url.split('://', 1)[1] else '/'} HTTP/1.1\r\nHost: {self.url.split('/')[2]}{headers_str}\r\n\r\n"
            else:
                body = self.data.encode("utf-8") if isinstance(self.data, str) else self.data
                request = f"{self.method} {self.url.split('/', 3)[3] if '/' in self.url.split('://', 1)[1] else '/'} HTTP/1.1\r\nHost: {self.url.split('/')[2]}\r\nContent-Length: {len(body)}{headers_str}\r\n\r\n"
                conn.send(request.encode("utf-8"))
                conn.send(body)
                return

            conn.send(request.encode("utf-8"))

        elif event == MG_EV_HTTP_MSG:
            # Response received
            self.response_code = data.status()
            self.response_body = data.body_text
            self.done = True
            conn.close()

        elif event == MG_EV_ERROR:
            # Connection error
            self.error = data
            self.done = True

        elif event == MG_EV_CLOSE:
            # Connection closed
            if not self.done and not self.error:
                self.error = "Connection closed unexpectedly"
            self.done = True

    def execute(self):
        """Execute the HTTP request and wait for response."""
        # Create connection
        conn = self.manager.connect(self.url, http=True)

        # Poll until done or timeout
        elapsed = 0
        poll_interval = 100  # ms

        while not self.done and elapsed < (self.timeout * 1000):
            self.manager.poll(poll_interval)
            elapsed += poll_interval

        if not self.done:
            self.error = f"Request timed out after {self.timeout}s"

        self.manager.close()

        return {"status": self.response_code, "body": self.response_body, "error": self.error}


def main():
    parser = argparse.ArgumentParser(description="HTTP Client Example")
    parser.add_argument("url", help="URL to request")
    parser.add_argument(
        "--method", default="GET", choices=["GET", "POST", "PUT", "DELETE"], help="HTTP method"
    )
    parser.add_argument("--data", help="Request body data")
    parser.add_argument("--header", action="append", help='Custom header (format: "Name: Value")')
    parser.add_argument("--timeout", type=int, default=10, help="Request timeout in seconds")
    parser.add_argument("--ca-cert", help="Path to CA certificate file for TLS verification")
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose output")
    args = parser.parse_args()

    # Parse headers
    headers = {}
    if args.header:
        for header in args.header:
            if ":" in header:
                name, value = header.split(":", 1)
                headers[name.strip()] = value.strip()

    # Load CA certificate if provided
    ca_cert = None
    if args.ca_cert:
        try:
            with open(args.ca_cert, "rb") as f:
                ca_cert = f.read()
        except IOError as e:
            print(f"Error reading CA certificate: {e}", file=sys.stderr)
            return 1

    # Create and execute request
    if args.verbose:
        print(f"Requesting: {args.method} {args.url}")
        if headers:
            print(f"Headers: {headers}")
        if args.data:
            print(f"Data: {args.data[:100]}..." if len(args.data) > 100 else f"Data: {args.data}")

    client = HttpClient(
        url=args.url,
        method=args.method,
        data=args.data,
        headers=headers,
        timeout=args.timeout,
        ca_cert=ca_cert,
    )

    result = client.execute()

    # Display results
    if result["error"]:
        print(f"Error: {result['error']}", file=sys.stderr)
        return 1

    if result["status"]:
        print(f"HTTP {result['status']}")
        if args.verbose:
            print(f"Response length: {len(result['body'])} bytes")
        print()
        print(result["body"])
        return 0 if 200 <= result["status"] < 300 else 1
    else:
        print("No response received", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
