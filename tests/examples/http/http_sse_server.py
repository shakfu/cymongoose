#!/usr/bin/env python3
"""Example Server-Sent Events (SSE) server.

This example demonstrates:
1. Server-Sent Events for real-time updates
2. Keeping connections alive for streaming
3. Periodic timer-based event broadcasting
4. HTML client with EventSource API

Usage:
    python http_sse_server.py [-l LISTEN_URL]

Example:
    python http_sse_server.py -l http://0.0.0.0:8000

    # Open browser to http://localhost:8000
    # Or test with curl:
    curl http://localhost:8000/events

Translation from C patterns for SSE in Mongoose (commonly used in device dashboards).

Server-Sent Events (SSE) is a standard for pushing updates from server to client
over HTTP. The client uses the EventSource JavaScript API to receive events.
"""

import argparse
import signal
from datetime import datetime

from cymongoose import (
    MG_EV_HTTP_MSG,
    Manager,
)

# Default configuration
DEFAULT_LISTEN = "http://0.0.0.0:8000"

# Global state
shutdown_requested = False
sse_connections = set()  # Active SSE connections
event_counter = 0


def signal_handler(sig, frame):
    """Handle shutdown signals (Ctrl+C, SIGTERM)."""
    global shutdown_requested
    shutdown_requested = True


def send_sse_event(conn, event_type, data):
    """Send a Server-Sent Event.

    Args:
        conn: Connection object
        event_type: Event type (e.g., 'message', 'update')
        data: Event data (string)
    """
    # SSE format:
    # event: type\n
    # data: payload\n
    # \n
    try:
        conn.http_sse(event_type, data)
    except RuntimeError:
        # Connection closed
        pass


def broadcast_event(event_type, data):
    """Broadcast an event to all SSE connections.

    Args:
        event_type: Event type
        data: Event data
    """
    closed_connections = []

    for conn in sse_connections:
        try:
            send_sse_event(conn, event_type, data)
        except RuntimeError:
            # Connection closed, mark for removal
            closed_connections.append(conn)

    # Remove closed connections
    for conn in closed_connections:
        sse_connections.discard(conn)


def timer_callback(manager, config):
    """Timer callback for periodic updates.

    Args:
        manager: Manager object
        config: Server configuration
    """
    global event_counter

    if not sse_connections:
        return

    event_counter += 1

    # Send periodic update to all SSE clients
    timestamp = datetime.now().isoformat()
    data = f"Event #{event_counter} at {timestamp}"

    broadcast_event("update", data)

    print(f"Broadcast event #{event_counter} to {len(sse_connections)} client(s)")


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

        if hm.uri == "/events":
            # SSE endpoint - keep connection alive and stream events
            print(f"[{conn.id}] SSE client connected")

            # Send SSE headers
            headers = {
                "Content-Type": "text/event-stream",
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
            }

            # Send headers manually (don't close connection)
            header_str = "HTTP/1.1 200 OK\r\n"
            for key, value in headers.items():
                header_str += f"{key}: {value}\r\n"
            header_str += "\r\n"
            conn.send(header_str.encode("utf-8"))

            # Send initial event
            send_sse_event(conn, "connected", "Welcome to SSE server!")

            # Add to active connections
            sse_connections.add(conn)

        elif hm.uri == "/trigger":
            # Endpoint to manually trigger an event
            broadcast_event("manual", "Manually triggered event")
            conn.reply(200, "Event sent to all clients\n")

        elif hm.uri == "/stats":
            # Stats endpoint
            stats = {
                "active_connections": len(sse_connections),
                "events_sent": event_counter,
            }

            import json

            conn.reply(
                200,
                json.dumps(stats, indent=2) + "\n",
                headers={"Content-Type": "application/json"},
            )

        elif hm.uri == "/":
            # Serve HTML client
            html = """<!DOCTYPE html>
<html>
<head>
    <title>Server-Sent Events Demo</title>
    <style>
        body { font-family: Arial, sans-serif; margin: 20px; }
        #events { border: 1px solid #ccc; padding: 10px; height: 300px; overflow-y: scroll; }
        .event { margin: 5px 0; padding: 5px; background: #f0f0f0; }
        .timestamp { color: #666; font-size: 0.9em; }
    </style>
</head>
<body>
    <h1>Server-Sent Events Demo</h1>
    <p>Connection status: <span id="status">Connecting...</span></p>
    <p>Events received: <span id="count">0</span></p>
    <button onclick="trigger()">Trigger Manual Event</button>
    <button onclick="clearEvents()">Clear Events</button>
    <h2>Events:</h2>
    <div id="events"></div>

    <script>
        let eventCount = 0;
        const eventsDiv = document.getElementById('events');
        const statusSpan = document.getElementById('status');
        const countSpan = document.getElementById('count');

        // Create EventSource connection
        const eventSource = new EventSource('/events');

        eventSource.addEventListener('connected', function(e) {
            statusSpan.textContent = 'Connected';
            statusSpan.style.color = 'green';
            addEvent('System', e.data);
        });

        eventSource.addEventListener('update', function(e) {
            addEvent('Update', e.data);
        });

        eventSource.addEventListener('manual', function(e) {
            addEvent('Manual', e.data);
        });

        eventSource.onerror = function(e) {
            statusSpan.textContent = 'Error/Disconnected';
            statusSpan.style.color = 'red';
        };

        function addEvent(type, data) {
            eventCount++;
            countSpan.textContent = eventCount;

            const eventDiv = document.createElement('div');
            eventDiv.className = 'event';
            eventDiv.innerHTML = `<strong>${type}:</strong> ${data} ` +
                `<span class="timestamp">(${new Date().toLocaleTimeString()})</span>`;
            eventsDiv.insertBefore(eventDiv, eventsDiv.firstChild);
        }

        function trigger() {
            fetch('/trigger').then(() => console.log('Event triggered'));
        }

        function clearEvents() {
            eventsDiv.innerHTML = '';
            eventCount = 0;
            countSpan.textContent = '0';
        }
    </script>
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
    parser = argparse.ArgumentParser(description="Server-Sent Events server")
    parser.add_argument(
        "-l", "--listen", default=DEFAULT_LISTEN, help=f"Listen URL (default: {DEFAULT_LISTEN})"
    )
    parser.add_argument(
        "-i",
        "--interval",
        type=int,
        default=5,
        help="Event broadcast interval in seconds (default: 5)",
    )

    args = parser.parse_args()

    # Configuration
    config = {
        "listen": args.listen,
        "interval": args.interval,
        "manager": None,
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

        # Add timer for periodic broadcasts
        manager.timer_add(
            args.interval * 1000,  # Convert to milliseconds
            repeat=True,
            run_now=False,
            callback=lambda: timer_callback(manager, config),
        )

        print(f"SSE Server started on {args.listen}")
        print(f"Broadcasting events every {args.interval} seconds")
        print("Press Ctrl+C to exit")
        print()
        print("Open browser to: http://localhost:8000")
        print("Or test with: curl http://localhost:8000/events")

        # Event loop
        while not shutdown_requested:
            manager.poll(100)

        print("\nShutting down...")

    finally:
        sse_connections.clear()
        manager.close()
        print("Server stopped cleanly")


if __name__ == "__main__":
    main()
