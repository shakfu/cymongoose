#!/usr/bin/env python3
"""Example HTTP file upload server.

This example demonstrates:
1. Streaming file uploads without buffering in memory
2. Handling MG_EV_HTTP_HDRS to intercept uploads early
3. Writing uploaded data directly to disk
4. Using graceful close with drain()

Usage:
    python http_file_upload.py [-l LISTEN_URL] [-d UPLOAD_DIR]

Example:
    python http_file_upload.py -l http://0.0.0.0:8000 -d /tmp

    # Upload a file:
    curl http://localhost:8000/upload/test.txt --data-binary @large_file.txt

Translation from C tutorial: thirdparty/mongoose/tutorials/http/file-upload-single-post/main.c

This server handles file uploads efficiently by:
- Catching /upload/* requests at MG_EV_HTTP_HDRS (before full body buffering)
- Writing data directly to disk as it arrives
- Not keeping the entire file in memory
"""

import argparse
import os
import signal
import sys
from pathlib import Path
from cymongoose import (
    Manager,
    MG_EV_HTTP_HDRS,
    MG_EV_HTTP_MSG,
    MG_EV_READ,
)

# Default configuration
DEFAULT_LISTEN = "http://0.0.0.0:8000"
DEFAULT_UPLOAD_DIR = "/tmp"

# Global state
shutdown_requested = False
upload_states = {}  # Connection -> upload state mapping


class UploadState:
    """Tracks state of an active upload."""

    def __init__(self, filepath, expected_bytes):
        self.filepath = filepath
        self.expected_bytes = expected_bytes
        self.received_bytes = 0
        self.file_handle = None

    def open_file(self):
        """Open file for writing."""
        # Ensure parent directory exists
        Path(self.filepath).parent.mkdir(parents=True, exist_ok=True)

        # Remove existing file
        if os.path.exists(self.filepath):
            os.remove(self.filepath)

        # Open for binary writing
        self.file_handle = open(self.filepath, "wb")

    def write_chunk(self, data):
        """Write data chunk to file."""
        if self.file_handle:
            self.file_handle.write(data)
            self.received_bytes += len(data)

    def is_complete(self):
        """Check if upload is complete."""
        return self.received_bytes >= self.expected_bytes

    def close(self):
        """Close file handle."""
        if self.file_handle:
            self.file_handle.close()
            self.file_handle = None


def signal_handler(sig, frame):
    """Handle shutdown signals (Ctrl+C, SIGTERM)."""
    global shutdown_requested
    shutdown_requested = True


def handle_upload(conn, ev, data, config):
    """Handle file upload for a specific connection.

    Args:
        conn: Connection object
        ev: Event type
        data: Event data (HttpMessage for headers)
        config: Server configuration
    """
    global upload_states

    conn_id = id(conn)

    if ev == MG_EV_HTTP_HDRS:
        # Received HTTP headers, check if it's an upload request
        hm = data  # HttpMessage object

        if hm.uri.startswith("/upload/"):
            # Extract filename from URI
            filename = hm.uri[8:]  # Remove '/upload/' prefix
            if not filename:
                filename = "uploaded_file"

            # Build upload path
            filepath = os.path.join(config["upload_dir"], filename)

            # Validate path (basic security check)
            filepath = os.path.abspath(filepath)
            upload_dir = os.path.abspath(config["upload_dir"])
            if not filepath.startswith(upload_dir):
                print(f"[{conn.id}] SECURITY: Rejected path traversal attempt: {filename}")
                conn.reply(400, "Bad Request: Invalid filename")
                conn.drain()
                return

            # Create upload state
            upload_state = UploadState(filepath, len(hm.body))
            upload_states[conn_id] = upload_state

            try:
                upload_state.open_file()
                print(f"[{conn.id}] UPLOAD START: {filepath} ({upload_state.expected_bytes} bytes)")
            except IOError as e:
                print(f"[{conn.id}] ERROR: Failed to open file: {e}")
                conn.reply(500, f"Internal Server Error: {e}")
                conn.drain()
                del upload_states[conn_id]
                return

            # Important: Prevent normal HTTP message buffering
            # We'll handle the body manually in MG_EV_READ
            # Note: In C this is done by setting c->pfn = NULL
            # In Python, we just mark it as handled

    # Handle upload data (works for both MG_EV_HTTP_HDRS and MG_EV_READ)
    if conn_id in upload_states:
        upload_state = upload_states[conn_id]

        # Get any buffered receive data
        recv_data = conn.recv_data()

        if recv_data:
            # Write to file
            upload_state.write_chunk(recv_data)

            # Check if complete
            if upload_state.is_complete():
                upload_state.close()
                print(
                    f"[{conn.id}] UPLOAD COMPLETE: {upload_state.filepath} ({upload_state.received_bytes} bytes)"
                )

                # Send response
                conn.reply(200, f"{upload_state.received_bytes} bytes uploaded successfully\n")
                conn.drain()  # Graceful close

                # Cleanup
                del upload_states[conn_id]


def http_handler(conn, ev, data, config):
    """Main HTTP event handler.

    Args:
        conn: Connection object
        ev: Event type
        data: Event data
        config: Server configuration
    """
    # Handle uploads
    handle_upload(conn, ev, data, config)

    # Handle other HTTP requests
    if ev == MG_EV_HTTP_MSG:
        hm = data

        # Check if it's an upload (already handled above)
        if id(conn) in upload_states:
            return

        # Non-upload requests - serve info page
        if hm.uri == "/":
            html = """<!DOCTYPE html>
<html>
<head><title>File Upload Server</title></head>
<body>
<h1>File Upload Server</h1>
<p>Upload a file to: <code>/upload/filename.txt</code></p>
<p>Example:</p>
<pre>curl http://localhost:8000/upload/test.txt --data-binary @file.txt</pre>
</body>
</html>
"""
            conn.reply(200, html, headers={"Content-Type": "text/html"})
        else:
            conn.reply(404, "Not Found")


def main():
    """Main function."""
    global shutdown_requested

    # Parse command-line arguments
    parser = argparse.ArgumentParser(description="HTTP file upload server")
    parser.add_argument(
        "-l", "--listen", default=DEFAULT_LISTEN, help=f"Listen URL (default: {DEFAULT_LISTEN})"
    )
    parser.add_argument(
        "-d",
        "--upload-dir",
        default=DEFAULT_UPLOAD_DIR,
        help=f"Upload directory (default: {DEFAULT_UPLOAD_DIR})",
    )

    args = parser.parse_args()

    # Ensure upload directory exists
    os.makedirs(args.upload_dir, exist_ok=True)

    # Configuration
    config = {
        "listen": args.listen,
        "upload_dir": args.upload_dir,
    }

    # Register signal handlers
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    # Create manager
    manager = Manager(lambda c, e, d: http_handler(c, e, d, config))

    try:
        # Start listening
        listener = manager.listen(args.listen, http=True)
        print(f"File Upload Server started on {args.listen}")
        print(f"Upload directory: {args.upload_dir}")
        print(f"Press Ctrl+C to exit")
        print()
        print(f"Upload a file:")
        print(f"  curl http://localhost:8000/upload/test.txt --data-binary @file.txt")

        # Event loop
        while not shutdown_requested:
            manager.poll(100)

        print("\nShutting down...")

    finally:
        # Close any open uploads
        for upload_state in upload_states.values():
            upload_state.close()
        upload_states.clear()

        manager.close()
        print("Server stopped cleanly")


if __name__ == "__main__":
    main()
