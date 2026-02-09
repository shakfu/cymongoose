#!/usr/bin/env python3
"""
WebSocket Timer Broadcasting Example - Periodic broadcasts to all connected clients.

Python translation of: thirdparty/mongoose/tutorials/core/timers/main.c

Features demonstrated:
- Periodic timer broadcasting to WebSocket clients
- Connection tracking with userdata
- Timer API with MG_TIMER_REPEAT
- Broadcasting to multiple connections
- Real-time push updates

Usage:
    python websocket_broadcast.py
    python websocket_broadcast.py --port 8080 --interval 2

Test with multiple browser tabs at http://localhost:8000/
Each tab will receive periodic broadcast messages.
"""

import argparse
import signal
import sys
import time
from pathlib import Path

# Add src to path for development
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from cymongoose import (
    MG_EV_CLOSE,
    MG_EV_HTTP_MSG,
    MG_EV_WS_MSG,
    MG_EV_WS_OPEN,
    Manager,
)

shutdown_requested = False


def signal_handler(sig, frame):
    global shutdown_requested
    shutdown_requested = True


class BroadcastServer:
    """WebSocket server with timer-based broadcasting."""

    def __init__(self, port=8000, interval=1):
        self.port = port
        self.interval = interval
        self.manager = None
        self.ws_clients = set()
        self.broadcast_count = 0

    def broadcast_timer(self):
        """Timer callback - broadcast message to all connected clients."""
        self.broadcast_count += 1
        timestamp = time.strftime("%H:%M:%S")
        message = (
            f"[{timestamp}] Broadcast #{self.broadcast_count} to {len(self.ws_clients)} clients"
        )

        print(message)

        # Send to all connected WebSocket clients
        disconnected = []
        for conn in self.ws_clients:
            try:
                conn.ws_send(message)
            except RuntimeError:
                # Connection closed
                disconnected.append(conn)

        # Remove disconnected clients
        for conn in disconnected:
            self.ws_clients.discard(conn)
            print(f"Removed disconnected client (remaining: {len(self.ws_clients)})")

    def handler(self, conn, event, data):
        """Event handler for HTTP and WebSocket connections."""
        if event == MG_EV_HTTP_MSG:
            uri = data.uri

            if uri == "/ws":
                # Upgrade to WebSocket
                conn.ws_upgrade(data)

            else:
                # Serve the HTML page
                conn.reply(200, HTML_PAGE, headers={"Content-Type": "text/html"})

        elif event == MG_EV_WS_OPEN:
            # New WebSocket connection
            self.ws_clients.add(conn)
            print(f"WebSocket client connected (total: {len(self.ws_clients)})")

            # Send welcome message
            conn.ws_send(f"Welcome! You are client #{len(self.ws_clients)}")

        elif event == MG_EV_WS_MSG:
            # Echo messages from clients
            msg = data
            print(f"Client message: {msg.text}")
            conn.ws_send(f"Echo: {msg.text}")

        elif event == MG_EV_CLOSE:
            # Connection closed
            if conn in self.ws_clients:
                self.ws_clients.discard(conn)
                print(f"WebSocket client disconnected (remaining: {len(self.ws_clients)})")

    def run(self):
        """Start the server and timer."""
        global shutdown_requested

        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)

        self.manager = Manager(self.handler)
        self.manager.listen(f"http://0.0.0.0:{self.port}", http=True)

        # Add periodic broadcast timer
        interval_ms = int(self.interval * 1000)
        self.manager.timer_add(
            interval_ms,
            self.broadcast_timer,
            repeat=True,
            run_now=False,  # Don't broadcast immediately
        )

        print(f"WebSocket broadcast server started on http://localhost:{self.port}")
        print(f"Broadcasting every {self.interval}s")
        print(f"Open http://localhost:{self.port}/ in multiple browser tabs")
        print("Press Ctrl+C to stop")

        try:
            while not shutdown_requested:
                self.manager.poll(100)
            print(f"\nShutting down... (broadcasted {self.broadcast_count} messages)")
        finally:
            self.ws_clients.clear()
            self.manager.close()
            print("Server stopped cleanly")


# HTML page served to clients
HTML_PAGE = """<!DOCTYPE html>
<html>
<head>
    <title>WebSocket Broadcast Demo</title>
    <style>
        body {
            font-family: Arial, sans-serif;
            max-width: 800px;
            margin: 50px auto;
            padding: 20px;
        }
        #status {
            padding: 10px;
            margin: 10px 0;
            border-radius: 5px;
        }
        .connected { background-color: #d4edda; color: #155724; }
        .disconnected { background-color: #f8d7da; color: #721c24; }
        #messages {
            border: 1px solid #ccc;
            height: 400px;
            overflow-y: scroll;
            padding: 10px;
            margin: 10px 0;
            background-color: #f9f9f9;
        }
        .message {
            padding: 5px;
            margin: 2px 0;
            border-left: 3px solid #007bff;
            padding-left: 10px;
        }
        .broadcast {
            border-left-color: #28a745;
            background-color: #d4edda;
        }
        .echo {
            border-left-color: #ffc107;
            background-color: #fff3cd;
        }
        .system {
            border-left-color: #6c757d;
            background-color: #e2e3e5;
        }
        #controls {
            margin: 10px 0;
        }
        input {
            width: 70%;
            padding: 8px;
            margin-right: 5px;
        }
        button {
            padding: 8px 15px;
            cursor: pointer;
        }
        .stats {
            margin-top: 20px;
            padding: 10px;
            background-color: #e7f3ff;
            border-radius: 5px;
        }
    </style>
</head>
<body>
    <h1>WebSocket Broadcast Demo</h1>
    <div id="status" class="disconnected">Status: Disconnected</div>

    <div id="messages"></div>

    <div id="controls">
        <input type="text" id="messageInput" placeholder="Type a message to echo...">
        <button onclick="sendMessage()">Send</button>
        <button onclick="clearMessages()">Clear</button>
    </div>

    <div class="stats">
        <strong>Statistics:</strong><br>
        Broadcasts received: <span id="broadcastCount">0</span><br>
        Total messages: <span id="totalCount">0</span><br>
        Connection time: <span id="connectionTime">0s</span>
    </div>

    <script>
        let ws;
        let broadcastCount = 0;
        let totalCount = 0;
        let connectTime = null;

        function connect() {
            ws = new WebSocket('ws://' + window.location.host + '/ws');

            ws.onopen = () => {
                document.getElementById('status').className = 'connected';
                document.getElementById('status').textContent = 'Status: Connected';
                connectTime = Date.now();
                addMessage('Connected to server - waiting for broadcasts...', 'system');
                updateConnectionTime();
            };

            ws.onmessage = (event) => {
                totalCount++;
                const msg = event.data;

                if (msg.startsWith('[')) {
                    // Broadcast message
                    broadcastCount++;
                    addMessage(msg, 'broadcast');
                    document.getElementById('broadcastCount').textContent = broadcastCount;
                } else if (msg.startsWith('Echo:')) {
                    // Echo response
                    addMessage(msg, 'echo');
                } else {
                    // System message
                    addMessage(msg, 'system');
                }

                document.getElementById('totalCount').textContent = totalCount;
            };

            ws.onclose = () => {
                document.getElementById('status').className = 'disconnected';
                document.getElementById('status').textContent = 'Status: Disconnected';
                addMessage('Disconnected from server', 'system');
                connectTime = null;
            };

            ws.onerror = (error) => {
                addMessage('Error: ' + error, 'system');
            };
        }

        function sendMessage() {
            const input = document.getElementById('messageInput');
            const message = input.value;
            if (message && ws && ws.readyState === WebSocket.OPEN) {
                ws.send(message);
                addMessage('You: ' + message, 'echo');
                input.value = '';
            }
        }

        function addMessage(text, type) {
            const messages = document.getElementById('messages');
            const div = document.createElement('div');
            div.className = 'message ' + type;
            div.textContent = text;
            messages.appendChild(div);
            messages.scrollTop = messages.scrollHeight;
        }

        function clearMessages() {
            document.getElementById('messages').innerHTML = '';
            broadcastCount = 0;
            totalCount = 0;
            document.getElementById('broadcastCount').textContent = '0';
            document.getElementById('totalCount').textContent = '0';
        }

        function updateConnectionTime() {
            if (connectTime) {
                const elapsed = Math.floor((Date.now() - connectTime) / 1000);
                document.getElementById('connectionTime').textContent = elapsed + 's';
                setTimeout(updateConnectionTime, 1000);
            }
        }

        document.getElementById('messageInput').addEventListener('keypress', (e) => {
            if (e.key === 'Enter') {
                sendMessage();
            }
        });

        // Connect on page load
        connect();
    </script>
</body>
</html>"""


def main():
    parser = argparse.ArgumentParser(description="WebSocket Broadcast Example")
    parser.add_argument("--port", type=int, default=8000, help="Port to listen on")
    parser.add_argument("--interval", type=float, default=1.0, help="Broadcast interval in seconds")
    args = parser.parse_args()

    server = BroadcastServer(port=args.port, interval=args.interval)
    server.run()


if __name__ == "__main__":
    main()
