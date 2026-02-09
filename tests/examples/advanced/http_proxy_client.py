#!/usr/bin/env python3
"""Example HTTP client that uses a proxy server.

This example demonstrates:
1. HTTP CONNECT method for proxy tunneling
2. Proxy authentication (if needed)
3. Two-stage connection: first to proxy, then through proxy to target
4. TLS initialization after tunnel establishment
5. Handling proxy responses

Usage:
    python http_proxy_client.py PROXY_URL TARGET_URL

Example:
    python http_proxy_client.py http://localhost:3128 http://www.example.com
    python http_proxy_client.py https://proxy.example.com:443 https://api.github.com

Translation from C tutorial: thirdparty/mongoose/tutorials/http/http-proxy-client/main.c

HTTP Proxy Protocol:
1. Client connects to proxy server
2. Client sends CONNECT request: "CONNECT target_host:target_port HTTP/1.1"
3. Proxy establishes connection to target
4. Proxy responds: "HTTP/1.1 200 Connection established"
5. Client sends actual HTTP request through tunnel
6. All subsequent data is forwarded between client and target

This is useful for:
- Corporate networks that require proxy for internet access
- Accessing servers through firewall
- Load balancing and caching
- Debugging and monitoring HTTP traffic
"""

import signal
import sys
import time

from cymongoose import (
    MG_EV_CLOSE,
    MG_EV_CONNECT,
    MG_EV_ERROR,
    MG_EV_HTTP_MSG,
    MG_EV_READ,
    Manager,
    TlsOpts,
)

# Global state
shutdown_requested = False
tunnel_established = False
response_received = False


def signal_handler(sig, frame):
    """Handle shutdown signals (Ctrl+C, SIGTERM)."""
    global shutdown_requested
    shutdown_requested = True


def parse_url(url):
    """Parse URL into scheme, host, port, and path.

    Args:
        url: URL string (e.g., "https://example.com:443/path")

    Returns:
        Tuple of (scheme, host, port, uri)
    """
    # Parse scheme
    if "://" in url:
        scheme, rest = url.split("://", 1)
    else:
        scheme = "http"
        rest = url

    # Parse host and path
    if "/" in rest:
        host_port, uri = rest.split("/", 1)
        uri = "/" + uri
    else:
        host_port = rest
        uri = "/"

    # Parse port
    if ":" in host_port:
        host, port_str = host_port.rsplit(":", 1)
        port = int(port_str)
    else:
        host = host_port
        port = 443 if scheme == "https" else 80

    return scheme, host, port, uri


def proxy_handler(conn, ev, data, config):
    """Proxy client event handler.

    Args:
        conn: Connection object
        ev: Event type
        data: Event data
        config: Client configuration
    """
    global tunnel_established, response_received

    target_url = config["target_url"]
    scheme, host, port, uri = parse_url(target_url)

    if ev == MG_EV_CONNECT:
        print(f"[{conn.id}] Connected to proxy")

        # Initialize TLS if proxy uses HTTPS
        proxy_scheme = parse_url(config["proxy_url"])[0]
        if proxy_scheme == "https" and conn.is_tls:
            proxy_host = parse_url(config["proxy_url"])[1]
            tls_opts = TlsOpts(name=proxy_host.encode("utf-8"), skip_verification=True)
            conn.tls_init(tls_opts)

        # Send CONNECT request to establish tunnel
        connect_request = f"CONNECT {host}:{port} HTTP/1.1\r\nHost: {host}:{port}\r\n\r\n"
        print(f"[{conn.id}] Sending CONNECT request:")
        print(f"  CONNECT {host}:{port} HTTP/1.1")
        conn.send(connect_request.encode("utf-8"))

    elif not tunnel_established and ev == MG_EV_READ:
        # Parse CONNECT response from proxy
        recv_data = conn.recv_data()
        if recv_data and b"\r\n\r\n" in recv_data:
            # Parse HTTP response
            response_line = recv_data.split(b"\r\n")[0].decode("utf-8", errors="ignore")
            print(f"[{conn.id}] Proxy response: {response_line}")

            if b"200" in recv_data or b"Connection established" in recv_data:
                print(f"[{conn.id}] Tunnel established!")
                tunnel_established = True

                # Initialize TLS if target uses HTTPS
                if scheme == "https":
                    print(f"[{conn.id}] Initializing TLS for target")
                    tls_opts = TlsOpts(name=host.encode("utf-8"), skip_verification=True)
                    conn.tls_init(tls_opts)

                # Send actual HTTP request to target through tunnel
                http_request = f"GET {uri} HTTP/1.0\r\nHost: {host}\r\n\r\n"
                print(f"[{conn.id}] Sending HTTP request to target:")
                print(f"  GET {uri} HTTP/1.0")
                print(f"  Host: {host}")
                conn.send(http_request.encode("utf-8"))
            else:
                print(f"[{conn.id}] Proxy connection failed: {response_line}")
                conn.close()

    elif ev == MG_EV_HTTP_MSG:
        # Received HTTP response from target server
        hm = data
        print(f"\n[{conn.id}] Response from target server:")
        print(f"  Status: {hm.uri}")  # In HTTP response, status is in uri field
        print(f"  Headers: {len(hm.headers)} headers")
        print(f"  Body length: {len(hm.body_bytes)} bytes")
        print()
        print("Response body:")
        print("-" * 60)
        # Print first 500 bytes of response
        body_preview = hm.body_bytes[:500].decode("utf-8", errors="ignore")
        print(body_preview)
        if len(hm.body_bytes) > 500:
            print(f"... ({len(hm.body_bytes) - 500} more bytes)")
        print("-" * 60)

        response_received = True
        conn.drain()

    elif ev == MG_EV_ERROR:
        error_msg = data if isinstance(data, str) else "Unknown error"
        print(f"[{conn.id}] ERROR: {error_msg}")

    elif ev == MG_EV_CLOSE:
        print(f"[{conn.id}] Connection closed")


def main():
    """Main function."""
    global shutdown_requested

    # Parse command-line arguments
    if len(sys.argv) != 3:
        print("Usage: python http_proxy_client.py PROXY_URL TARGET_URL")
        print()
        print("Examples:")
        print("  python http_proxy_client.py http://localhost:3128 http://www.example.com")
        print("  python http_proxy_client.py http://proxy.example.com:8080 https://api.github.com")
        sys.exit(1)

    proxy_url = sys.argv[1]
    target_url = sys.argv[2]

    print("Proxy client starting...")
    print(f"  Proxy:  {proxy_url}")
    print(f"  Target: {target_url}")
    print()

    config = {
        "proxy_url": proxy_url,
        "target_url": target_url,
    }

    # Register signal handlers
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    # Create manager
    manager = Manager()

    try:
        # Connect to proxy server
        manager.connect(
            proxy_url, handler=lambda c, e, d: proxy_handler(c, e, d, config), http=True
        )

        # Event loop - exit when response received or timeout
        start_time = time.time()
        timeout = 30  # 30 second timeout

        while not shutdown_requested and not response_received:
            manager.poll(100)

            # Timeout after 30 seconds
            if time.time() - start_time > timeout:
                print(f"\nTimeout after {timeout} seconds")
                break

        if response_received:
            print("\nRequest completed successfully!")
        elif shutdown_requested:
            print("\nInterrupted by user")

    finally:
        manager.close()


if __name__ == "__main__":
    main()
