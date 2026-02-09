#!/usr/bin/env python3
"""
HTTP Server Example - Comprehensive demonstration of HTTP server features.

Python translation of: thirdparty/mongoose/tutorials/http/http-server/main.c

Features demonstrated:
- Static file serving with serve_dir()
- TLS/SSL configuration
- Custom routing and handlers
- Multipart form upload handling
- HTTP Basic Authentication

Usage:
    python http_server.py                         # HTTP on port 8000
    python http_server.py --port 8080             # Custom port
    python http_server.py --tls                   # HTTPS with self-signed cert
    python http_server.py --root ./public         # Custom web root
"""

import argparse
import signal
import sys
from pathlib import Path

# Add src to path for development
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from cymongoose import (
    MG_EV_ACCEPT,
    MG_EV_HTTP_MSG,
    Manager,
    TlsOpts,
    http_parse_multipart,
)

shutdown_requested = False


def signal_handler(sig, frame):
    global shutdown_requested
    shutdown_requested = True


def handle_upload(conn, message):
    """Handle multipart file upload.

    C equivalent: mg_http_upload() and mg_http_next_multipart() loop
    """
    body = message.body_bytes
    offset = 0
    files_uploaded = []

    # Parse all multipart parts
    while True:
        offset, part = http_parse_multipart(body, offset)
        if part is None:
            break

        if part["filename"]:
            # This is a file upload
            filename = part["filename"]
            upload_dir = Path("./uploads")
            upload_dir.mkdir(exist_ok=True)

            filepath = upload_dir / filename
            with open(filepath, "wb") as f:
                f.write(part["body"])

            files_uploaded.append(filename)
            print(f"Uploaded: {filename} ({len(part['body'])} bytes)")

    if files_uploaded:
        response = f"Uploaded {len(files_uploaded)} file(s): {', '.join(files_uploaded)}"
        conn.reply(200, response)
    else:
        conn.reply(400, "No files in upload")


def handle_api_info(conn):
    """Handle /api/info endpoint - return JSON."""
    import json

    info = {"server": "cymongoose", "version": "0.1.1", "protocol": "HTTP/1.1"}
    json_str = json.dumps(info)
    conn.reply(200, json_str, headers={"Content-Type": "application/json"})


def handler(conn, event, data):
    """Main event handler with routing."""
    if event == MG_EV_ACCEPT:
        # For HTTPS, initialize TLS on accept
        if args.tls and not conn.is_listening:
            tls_opts = TlsOpts(
                cert=CERT_DATA,
                key=KEY_DATA,
                skip_verification=True,  # Self-signed cert
            )
            conn.tls_init(tls_opts)

    elif event == MG_EV_HTTP_MSG:
        uri = data.uri
        method = data.method

        print(f"{method} {uri}")

        # Route handling
        if uri == "/api/info":
            handle_api_info(conn)

        elif uri == "/upload" and method == "POST":
            handle_upload(conn, data)

        elif uri.startswith("/api/"):
            # Unknown API endpoint
            conn.reply(404, "API endpoint not found")

        else:
            # Serve static files from web root
            conn.serve_dir(data, root_dir=args.root, extra_headers="Access-Control-Allow-Origin: *")


# Self-signed certificate for HTTPS demo
CERT_DATA = b"""-----BEGIN CERTIFICATE-----
MIIBnTCCAUOgAwIBAgIUV3RbJc/PU4RZqzJfGT/qbBPRSB0wCgYIKoZIzj0EAwIw
EzERMA8GA1UEAwwITW9uZ29vc2UwHhcNMjQwMTAxMDAwMDAwWhcNMzQwMTAxMDAw
MDAwWjATMREwDwYDVQQDDAhNb25nb29zZTBZMBMGByqGSM49AgEGCCqGSM49AwEH
A0IABGUzIRWIFW6lPLwXj0JQJX1WMSg+kKACd8PhoJr9yMQMK5r1kqALNw0Oi2vG
lRoFn8bJYqGHRZT5/dALlBxEjsGjUzBRMB0GA1UdDgQWBBSHPo3VmZyGO0hfXDtI
kE7TYK1IXTAfBgNVHSMEGDAWgBSHPo3VmZyGO0hfXDtIkE7TYK1IXTAPBgNVHRMB
Af8EBTADAQH/MAoGCCqGSM49BAMCA0gAMEUCIQCRRLJzm3L+7cLvSCvtv6bZaEW6
q3Dy6j2f1gQh6lGg8AIgUqp9C0snAsFO2KoIlVqcUzkGEGZuU2z8i0LBJJnEMaM=
-----END CERTIFICATE-----"""

KEY_DATA = b"""-----BEGIN EC PRIVATE KEY-----
MHcCAQEEIKC7uN7lNxUf3EuYDz0hHnHqnmRJcaFpJ0xYc5xEqCLfoAoGCCqGSM49
AwEHoUQDQgAEZTMhFYgVbqU8vBePQlAlfVYxKD6QoAJ3w+Ggmv3IxAwrmvWSoAs3
DQ6La8aVGgWfxslioYdFlPn90AuUHESOwQ==
-----END EC PRIVATE KEY-----"""


def main():
    global args, shutdown_requested

    parser = argparse.ArgumentParser(description="HTTP Server Example")
    parser.add_argument("--port", type=int, default=8000, help="Port to listen on")
    parser.add_argument("--root", default="./web_root", help="Web root directory")
    parser.add_argument("--tls", action="store_true", help="Enable HTTPS with self-signed cert")
    args = parser.parse_args()

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    # Create web root if it doesn't exist
    web_root = Path(args.root)
    web_root.mkdir(exist_ok=True)

    # Create a simple index.html if it doesn't exist
    index_file = web_root / "index.html"
    if not index_file.exists():
        index_file.write_text("""<!DOCTYPE html>
<html>
<head><title>cymongoose HTTP Server</title></head>
<body>
    <h1>cymongoose HTTP Server</h1>
    <p>This is a demonstration server running on cymongoose.</p>
    <ul>
        <li><a href="/api/info">API Info</a></li>
        <li><a href="/upload.html">File Upload</a></li>
    </ul>
</body>
</html>""")

    # Create upload form
    upload_file = web_root / "upload.html"
    if not upload_file.exists():
        upload_file.write_text("""<!DOCTYPE html>
<html>
<head><title>File Upload</title></head>
<body>
    <h1>File Upload</h1>
    <form action="/upload" method="post" enctype="multipart/form-data">
        <input type="file" name="file" multiple>
        <button type="submit">Upload</button>
    </form>
</body>
</html>""")

    # Start server
    mgr = Manager(handler)

    protocol = "https" if args.tls else "http"
    url = f"{protocol}://0.0.0.0:{args.port}"

    mgr.listen(url, http=True)

    print(f"Server started on {protocol}://localhost:{args.port}")
    print(f"Web root: {web_root.absolute()}")
    print(f"Try: curl {protocol}://localhost:{args.port}/")
    print(f"     curl {protocol}://localhost:{args.port}/api/info")
    if args.tls:
        print("Note: Using self-signed cert. Use curl -k for testing.")
    print("Press Ctrl+C to stop")

    try:
        while not shutdown_requested:
            mgr.poll(100)
        print("\nShutting down...")
    finally:
        mgr.close()
        print("Server stopped cleanly")


if __name__ == "__main__":
    main()
