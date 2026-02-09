#!/usr/bin/env python3
"""Example SNTP (Network Time Protocol) client.

This example demonstrates:
1. Connecting to SNTP server over UDP
2. Requesting current time
3. Timer-based reconnection and periodic sync
4. Time synchronization for embedded systems

Usage:
    python sntp_client.py [-s SERVER] [-i INTERVAL]

Example:
    python sntp_client.py -s udp://time.google.com:123 -i 5

Translation from C tutorial: thirdparty/mongoose/tutorials/udp/sntp-time-sync/main.c

SNTP is critical for embedded devices that need TLS but don't have a real-time clock.
Time synchronization allows time() to work correctly.
"""

import argparse
import signal
from datetime import datetime

from cymongoose import (
    MG_EV_CLOSE,
    MG_EV_ERROR,
    MG_EV_SNTP_TIME,
    Manager,
)

# Default configuration
DEFAULT_SERVER = "udp://time.google.com:123"
DEFAULT_INTERVAL = 30  # 30 seconds

# Global state
shutdown_requested = False
sntp_conn = None
boot_timestamp = 0  # Unix epoch of boot time
last_sync_time = None


def signal_handler(sig, frame):
    """Handle shutdown signals (Ctrl+C, SIGTERM)."""
    global shutdown_requested
    shutdown_requested = True


def sntp_handler(conn, ev, data, config):
    """SNTP event handler.

    Args:
        conn: Connection object
        ev: Event type
        data: Event data
        config: Client configuration
    """
    global sntp_conn, boot_timestamp, last_sync_time

    if ev == MG_EV_SNTP_TIME:
        # Time received from server
        # data contains uint64 milliseconds from epoch
        time_ms = data

        # Update boot timestamp (for embedded systems without RTC)
        # This allows time() to work correctly by calculating: boot_time + uptime
        boot_timestamp = time_ms / 1000.0

        # Convert to datetime for display
        dt = datetime.fromtimestamp(time_ms / 1000.0)
        last_sync_time = dt

        print(f"[{conn.id}] SNTP time received: {dt.isoformat()}")
        print(f"[{conn.id}] Time: {time_ms} ms from epoch")
        print(f"[{conn.id}] Boot timestamp: {boot_timestamp}")

    elif ev == MG_EV_ERROR:
        error_msg = data if isinstance(data, str) else "Unknown error"
        print(f"[{conn.id}] ERROR: {error_msg}")

    elif ev == MG_EV_CLOSE:
        print(f"[{conn.id}] Connection closed")
        sntp_conn = None


def timer_callback(manager, config):
    """Timer callback for periodic SNTP synchronization.

    Args:
        manager: Manager object
        config: Client configuration
    """
    global sntp_conn

    if sntp_conn is None:
        # Create new connection
        print(f"Connecting to {config['server']}...")
        try:
            sntp_conn = manager.sntp_connect(
                config["server"], handler=lambda c, e, d: sntp_handler(c, e, d, config)
            )
            print(f"[{sntp_conn.id}] SNTP connection created")
        except RuntimeError as e:
            print(f"Failed to connect: {e}")
            return
    else:
        # Send time request on existing connection
        try:
            print(f"[{sntp_conn.id}] Sending SNTP request...")
            sntp_conn.sntp_request()
        except RuntimeError as e:
            print(f"Failed to send request: {e}")
            sntp_conn = None


def main():
    """Main function."""
    global shutdown_requested

    # Parse command-line arguments
    parser = argparse.ArgumentParser(description="SNTP client example")
    parser.add_argument(
        "-s",
        "--server",
        default=DEFAULT_SERVER,
        help=f"SNTP server URL (default: {DEFAULT_SERVER})",
    )
    parser.add_argument(
        "-i",
        "--interval",
        type=int,
        default=DEFAULT_INTERVAL,
        help=f"Sync interval in seconds (default: {DEFAULT_INTERVAL})",
    )

    args = parser.parse_args()

    # Configuration
    config = {
        "server": args.server,
        "interval": args.interval,
    }

    # Register signal handlers
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    # Create manager
    manager = Manager()

    try:
        # Add timer for periodic sync
        manager.timer_add(
            args.interval * 1000,  # Convert to milliseconds
            repeat=True,
            run_now=True,  # Run immediately on start
            callback=lambda: timer_callback(manager, config),
        )

        print("SNTP Client started")
        print(f"  Server: {config['server']}")
        print(f"  Sync interval: {config['interval']} seconds")
        print("Press Ctrl+C to exit")
        print()

        # Event loop
        while not shutdown_requested:
            manager.poll(100)

        print("\nShutting down...")

    finally:
        manager.close()
        if last_sync_time:
            print(f"Last synchronized: {last_sync_time.isoformat()}")
        print("Client stopped cleanly")


if __name__ == "__main__":
    main()
