#!/usr/bin/env python3
"""Example DNS resolution client.

This example demonstrates:
1. Asynchronous DNS hostname resolution
2. Resolution cancellation
3. Timer-based periodic resolution
4. Error handling for invalid hostnames

Usage:
    python dns_client.py [-h HOSTNAME] [-i INTERVAL]

Example:
    python dns_client.py -h google.com -i 5
    python dns_client.py -h tcp://example.com:443

Translation from Mongoose DNS API patterns used throughout tutorials.

DNS resolution is critical for:
- HTTP/HTTPS clients connecting to domain names
- MQTT clients connecting to brokers by hostname
- Any network client using hostnames instead of IP addresses

This example demonstrates standalone DNS resolution without creating
an actual connection - useful for network utilities and diagnostics.
"""

import argparse
import signal
import time
from cymongoose import (
    Manager,
    MG_EV_RESOLVE,
    MG_EV_ERROR,
)

# Default configuration
DEFAULT_HOSTNAME = "google.com"
DEFAULT_INTERVAL = 10  # 10 seconds

# Global state
shutdown_requested = False
dns_conn = None


def signal_handler(sig, frame):
    """Handle shutdown signals (Ctrl+C, SIGTERM)."""
    global shutdown_requested
    shutdown_requested = True


def dns_handler(conn, ev, data, config):
    """DNS resolution event handler.

    Args:
        conn: Connection object
        ev: Event type
        data: Event data
        config: Client configuration
    """
    if ev == MG_EV_RESOLVE:
        # Resolution completed
        # data contains the resolved address as a string
        resolved_addr = data if isinstance(data, str) else str(data)

        hostname = config.get("hostname", "unknown")
        print(f"[{conn.id}] DNS resolution for '{hostname}' succeeded")
        print(f"[{conn.id}] Resolved to: {resolved_addr}")

    elif ev == MG_EV_ERROR:
        # Resolution failed
        error_msg = data if isinstance(data, str) else "Unknown error"
        hostname = config.get("hostname", "unknown")
        print(f"[{conn.id}] DNS resolution for '{hostname}' failed: {error_msg}")


def timer_callback(manager, config):
    """Timer callback for periodic DNS resolution.

    Args:
        manager: Manager object
        config: Client configuration
    """
    global dns_conn

    # We need a connection to trigger resolution
    # Use a dummy listener connection that stays alive
    if dns_conn is None:
        # Create a listener connection (stays alive, doesn't accept connections)
        # This is a workaround since DNS resolution requires a connection object
        dns_conn = manager.listen(
            "tcp://127.0.0.1:0",  # Bind to any free port
            handler=lambda c, e, d: dns_handler(c, e, d, config),
        )
        print(f"[{dns_conn.id}] DNS resolver connection created")

    # Trigger DNS resolution
    try:
        hostname = config["hostname"]
        print(f"\n[{dns_conn.id}] Resolving '{hostname}'...")
        dns_conn.resolve(hostname)
    except RuntimeError as e:
        print(f"Failed to resolve: {e}")


def main():
    """Main function."""
    global shutdown_requested

    # Parse command-line arguments
    parser = argparse.ArgumentParser(description="DNS resolution client example")
    parser.add_argument(
        "-H",
        "--hostname",
        default=DEFAULT_HOSTNAME,
        help=f"Hostname to resolve (default: {DEFAULT_HOSTNAME})",
    )
    parser.add_argument(
        "-i",
        "--interval",
        type=int,
        default=DEFAULT_INTERVAL,
        help=f"Resolution interval in seconds (default: {DEFAULT_INTERVAL})",
    )
    parser.add_argument("--once", action="store_true", help="Resolve once and exit (don't repeat)")

    args = parser.parse_args()

    # Configuration
    config = {
        "hostname": args.hostname,
        "interval": args.interval,
        "once": args.once,
    }

    # Register signal handlers
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    # Create manager
    manager = Manager()

    try:
        # Add timer for periodic resolution
        timer = manager.timer_add(
            args.interval * 1000,  # Convert to milliseconds
            repeat=not args.once,
            run_now=True,  # Resolve immediately on start
            callback=lambda: timer_callback(manager, config),
        )

        print(f"DNS Resolution Client started")
        print(f"  Hostname: {config['hostname']}")
        if not args.once:
            print(f"  Resolution interval: {config['interval']} seconds")
            print(f"Press Ctrl+C to exit")
        print()

        # Event loop
        start_time = time.time()
        while not shutdown_requested:
            manager.poll(100)

            # If --once, exit after 5 seconds max (allows time for resolution)
            if args.once and time.time() - start_time > 5:
                break

        if not args.once:
            print("\nShutting down...")

    finally:
        manager.close()
        print("Client stopped cleanly")


if __name__ == "__main__":
    main()
