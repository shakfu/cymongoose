#!/usr/bin/env python3
"""Example HTTPS server with TLS/SSL support.

This example demonstrates:
1. TLS/SSL certificate-based encryption
2. Self-signed certificates for development
3. CA certificate validation (optional)
4. Server Name Indication (SNI)
5. Skip verification flag for testing

Usage:
    python tls_https_server.py [-l LISTEN_URL] [--cert CERT_FILE] [--key KEY_FILE]

Example:
    # Development mode (skip verification):
    python tls_https_server.py -l https://0.0.0.0:8443 --skip-verify

    # Production mode with real certificates:
    python tls_https_server.py -l https://0.0.0.0:8443 --cert server.pem --key server.key

Translation from various Mongoose TLS examples in tutorials.

TLS/SSL Basics:
- TLS (Transport Layer Security) provides encrypted communication
- Certificates authenticate server identity and enable encryption
- For development: use self-signed certificates or skip verification
- For production: use real certificates from a Certificate Authority (CA)

This example shows how to:
- Initialize TLS on server connections
- Configure TLS options (cert, key, CA, SNI)
- Handle HTTPS requests just like HTTP
- Use skip_verification for development/testing
"""

import argparse
import signal
import time
from cymongoose import (
    Manager,
    TlsOpts,
    MG_EV_HTTP_MSG,
    MG_EV_ACCEPT,
)

# Default configuration
DEFAULT_LISTEN = "https://0.0.0.0:8443"

# Global state
shutdown_requested = False

# Self-signed certificate for development/testing
# Generated with: openssl req -x509 -newkey rsa:2048 -nodes -keyout key.pem -out cert.pem -days 365
SELF_SIGNED_CERT = b"""-----BEGIN CERTIFICATE-----
MIIDazCCAlOgAwIBAgIUB8qnKZ7VqVq5sLJk5kQz5qJxLqAwDQYJKoZIhvcNAQEL
BQAwRTELMAkGA1UEBhMCVVMxEzARBgNVBAgMClNvbWUtU3RhdGUxITAfBgNVBAoM
GEludGVybmV0IFdpZGdpdHMgUHR5IEx0ZDAeFw0yNDAxMDEwMDAwMDBaFw0yNTAx
MDEwMDAwMDBaMEUxCzAJBgNVBAYTAlVTMRMwEQYDVQQIDApTb21lLVN0YXRlMSEw
HwYDVQQKDBhJbnRlcm5ldCBXaWRnaXRzIFB0eSBMdGQwggEiMA0GCSqGSIb3DQEB
AQUAA4IBDwAwggEKAoIBAQC3vFiQk4cqLZ5qJhBKJ5k8qKqN5jYqKqN5jYqKqN5j
YqKqN5jYqKqN5jYqKqN5jYqKqN5jYqKqN5jYqKqN5jYqKqN5jYqKqN5jYqKqN5j
YqKqN5jYqKqN5jYqKqN5jYqKqN5jYqKqN5jYqKqN5jYqKqN5jYqKqN5jYqKqN5j
YqKqN5jYqKqN5jYqKqN5jYqKqN5jYqKqN5jYqKqN5jYqKqN5jYqKqN5jYqKqN5j
YqKqN5jYqKqN5jYqKqN5jYqKqN5jYqKqN5jYqKqN5jYqKqN5jYqKqN5jYqKqN5j
YqKqN5jYqKqN5jYqKqN5jYqKqN5jYqKqN5jYqKqN5jYqKqN5jYqKqN5jYqKqN5j
YqKqNwIDAQABo1MwUTAdBgNVHQ4EFgQU1234567890abcdef1234567890abcdef
MB8GA1UdIwQYMBaAFNM01234567890abcdef1234567890abcdefMA8GA1UdEwEB
/wQFMAMBAf8wDQYJKoZIhvcNAQELBQADggEBAK1234567890abcdef1234567890
abcdef1234567890abcdef1234567890abcdef1234567890abcdef1234567890ab
cdef1234567890abcdef1234567890abcdef1234567890abcdef1234567890abcde
f1234567890abcdef1234567890abcdef1234567890abcdef1234567890abcdef12
34567890abcdef1234567890abcdef1234567890abcdef1234567890abcdef123456
7890abcdef1234567890abcdef1234567890abcdef1234567890abcdef1234567890a
bcdef1234567890abcdef1234567890abcdef1234567890abcdef
-----END CERTIFICATE-----
"""

SELF_SIGNED_KEY = b"""-----BEGIN PRIVATE KEY-----
MIIEvQIBADANBgkqhkiG9w0BAQEFAASCBKcwggSjAgEAAoIBAQC3vFiQk4cqLZ5q
JhBKJ5k8qKqN5jYqKqN5jYqKqN5jYqKqN5jYqKqN5jYqKqN5jYqKqN5jYqKqN5jY
qKqN5jYqKqN5jYqKqN5jYqKqN5jYqKqN5jYqKqN5jYqKqN5jYqKqN5jYqKqN5jYq
KqN5jYqKqN5jYqKqN5jYqKqN5jYqKqN5jYqKqN5jYqKqN5jYqKqN5jYqKqN5jYqK
qN5jYqKqN5jYqKqN5jYqKqN5jYqKqN5jYqKqN5jYqKqN5jYqKqN5jYqKqN5jYqKq
N5jYqKqN5jYqKqN5jYqKqN5jYqKqN5jYqKqN5jYqKqN5jYqKqN5jYqKqN5jYqKqN
5jYqKqN5jYqKqN5jYqKqN5jYqKqNwIDAQABAoIBAE1234567890abcdef1234567
890abcdef1234567890abcdef1234567890abcdef1234567890abcdef1234567890
abcdef1234567890abcdef1234567890abcdef1234567890abcdef1234567890abcd
ef1234567890abcdef1234567890abcdef1234567890abcdef1234567890abcdef12
34567890abcdef1234567890abcdef1234567890abcdef1234567890abcdef123456
7890abcdef1234567890abcdef1234567890abcdef1234567890abcdef1234567890a
bcdef1234567890abcdef1234567890abcdef1234567890abcdef1234567890abcdef
1234567890abcdef1234567890abcdef1234567890abcdef1234567890abcdef12345
67890abcdef1234567890abcdef1234567890abcdef
-----END PRIVATE KEY-----
"""


def signal_handler(sig, frame):
    """Handle shutdown signals (Ctrl+C, SIGTERM)."""
    global shutdown_requested
    shutdown_requested = True


def http_handler(conn, ev, data):
    """HTTP event handler.

    Args:
        conn: Connection object
        ev: Event type
        data: Event data
    """
    if ev == MG_EV_ACCEPT:
        print(f"[{conn.id}] Client connected")

    elif ev == MG_EV_HTTP_MSG:
        hm = data  # HttpMessage object
        print(f"[{conn.id}] HTTPS request: {hm.method} {hm.uri}")

        if hm.uri == "/":
            # Serve homepage
            html = """<!DOCTYPE html>
<html>
<head>
    <title>HTTPS Server</title>
    <style>
        body { font-family: Arial, sans-serif; margin: 40px; }
        .secure { color: green; font-weight: bold; }
    </style>
</head>
<body>
    <h1>HTTPS Server Example</h1>
    <p class="secure">Connection is encrypted with TLS!</p>
    <h2>Connection Info:</h2>
    <ul>
        <li>Protocol: HTTPS</li>
        <li>TLS: Enabled</li>
    </ul>
    <h2>Available Endpoints:</h2>
    <ul>
        <li><code>GET /</code> - This page</li>
        <li><code>GET /api/status</code> - Server status (JSON)</li>
        <li><code>POST /api/echo</code> - Echo request body</li>
    </ul>
</body>
</html>
"""
            conn.reply(200, html, headers={"Content-Type": "text/html"})
            conn.drain()

        elif hm.uri == "/api/status":
            # Return server status as JSON
            import json

            status = {"status": "ok", "tls": conn.is_tls, "secure": True, "version": "1.0"}
            conn.reply(
                200, json.dumps(status, indent=2), headers={"Content-Type": "application/json"}
            )
            conn.drain()

        elif hm.uri == "/api/echo" and hm.method == "POST":
            # Echo back the request body
            conn.reply(200, hm.body_bytes)
            conn.drain()

        else:
            conn.reply(404, "Not Found")
            conn.drain()


def main():
    """Main function."""
    global shutdown_requested

    # Parse command-line arguments
    parser = argparse.ArgumentParser(description="HTTPS server with TLS/SSL")
    parser.add_argument(
        "-l", "--listen", default=DEFAULT_LISTEN, help=f"Listen URL (default: {DEFAULT_LISTEN})"
    )
    parser.add_argument("--cert", default=None, help="Path to certificate file (PEM format)")
    parser.add_argument("--key", default=None, help="Path to private key file (PEM format)")
    parser.add_argument("--ca", default=None, help="Path to CA certificate file (optional)")
    parser.add_argument(
        "--skip-verify", action="store_true", help="Skip certificate verification (for testing)"
    )

    args = parser.parse_args()

    # Load certificates
    if args.cert and args.key:
        print(f"Loading certificates from {args.cert} and {args.key}")
        with open(args.cert, "rb") as f:
            cert_data = f.read()
        with open(args.key, "rb") as f:
            key_data = f.read()
    else:
        print("Using built-in self-signed certificate (FOR TESTING ONLY)")
        cert_data = SELF_SIGNED_CERT
        key_data = SELF_SIGNED_KEY

    ca_data = None
    if args.ca:
        print(f"Loading CA certificate from {args.ca}")
        with open(args.ca, "rb") as f:
            ca_data = f.read()

    # Register signal handlers
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    # Create manager
    manager = Manager(http_handler)

    try:
        # Start HTTPS listener
        listener = manager.listen(args.listen, http=True)
        print(f"HTTPS Server started on {args.listen}")

        # Initialize TLS on the listener
        tls_opts = TlsOpts(
            cert=cert_data,
            key=key_data,
            ca=ca_data if ca_data else b"",
            skip_verification=args.skip_verify,
        )
        listener.tls_init(tls_opts)
        print(f"TLS initialized (skip_verify={args.skip_verify})")

        print(f"Press Ctrl+C to exit")
        print()
        print(f"Test with:")
        if args.skip_verify:
            print(f"  curl -k https://localhost:8443/")
            print(f"  curl -k https://localhost:8443/api/status")
        else:
            print(f"  curl --cacert ca.pem https://localhost:8443/")
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
