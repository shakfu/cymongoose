#!/usr/bin/env python3
"""
WebSocket Server Example - Echo server with REST API and static files.

Python translation of: thirdparty/mongoose/tutorials/websocket/websocket-server/main.c

Features demonstrated:
- WebSocket upgrade from HTTP
- Echo server pattern (text and binary)
- REST API alongside WebSocket
- Static file serving
- Mixed HTTP + WebSocket server

Usage:
    python websocket_server.py
    python websocket_server.py --port 8080
    python websocket_server.py --root ./public

Test with:
    # WebSocket client (requires websocket-client package)
    python -c "
    from websocket import create_connection
    ws = create_connection('ws://localhost:8000/ws')
    ws.send('Hello')
    print(ws.recv())
    ws.close()
    "

    # Or use browser JavaScript:
    # ws = new WebSocket('ws://localhost:8000/ws');
    # ws.onmessage = e => console.log(e.data);
    # ws.send('Hello');
"""

import argparse
import signal
import sys
from pathlib import Path

# Add src to path for development
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from cymongoose import (
    MG_EV_HTTP_MSG,
    MG_EV_WS_MSG,
    MG_EV_WS_OPEN,
    WEBSOCKET_OP_BINARY,
    WEBSOCKET_OP_TEXT,
    Manager,
)

shutdown_requested = False


def signal_handler(sig, frame):
    global shutdown_requested
    shutdown_requested = True


# Track connected WebSocket clients
ws_clients = set()


def handle_rest_api(conn, data):
    """Handle REST API endpoints."""
    uri = data.uri
    method = data.method

    if uri == "/api/stats":
        import json

        stats = {"websocket_clients": len(ws_clients), "endpoint": "/ws"}
        response = json.dumps(stats)
        conn.reply(200, response, headers={"Content-Type": "application/json"})

    elif uri == "/api/broadcast" and method == "POST":
        # Broadcast message to all WebSocket clients
        message = data.body_text
        broadcast_count = 0

        for ws_conn in ws_clients:
            try:
                ws_conn.ws_send(f"Broadcast: {message}")
                broadcast_count += 1
            except Exception:
                pass

        conn.reply(200, f"Broadcasted to {broadcast_count} clients")

    else:
        conn.reply(404, "API endpoint not found")


def handler(conn, event, data):
    """Main event handler for HTTP and WebSocket."""
    if event == MG_EV_HTTP_MSG:
        uri = data.uri
        method = data.method

        print(f"{method} {uri}")

        if uri == "/ws":
            # Upgrade to WebSocket
            conn.ws_upgrade(data)

        elif uri.startswith("/api/"):
            # Handle REST API
            handle_rest_api(conn, data)

        else:
            # Serve static files
            conn.serve_dir(data, root_dir=args.root, extra_headers="Cache-Control: max-age=3600")

    elif event == MG_EV_WS_OPEN:
        # WebSocket connection established
        ws_clients.add(conn)
        print(f"WebSocket connected (total: {len(ws_clients)})")

    elif event == MG_EV_WS_MSG:
        # WebSocket message received - echo it back
        msg = data
        print(
            f"WebSocket message: {msg.text[:50]}..."
            if len(msg.text) > 50
            else f"WebSocket message: {msg.text}"
        )

        # Echo back the message
        if msg.flags == WEBSOCKET_OP_TEXT:
            conn.ws_send(f"Echo: {msg.text}", op=WEBSOCKET_OP_TEXT)
        elif msg.flags == WEBSOCKET_OP_BINARY:
            conn.ws_send(msg.data, op=WEBSOCKET_OP_BINARY)

    # Note: Connection cleanup handled automatically by Manager on MG_EV_CLOSE
    # In production code, you might want to explicitly track and remove closed connections


def main():
    global args, shutdown_requested

    parser = argparse.ArgumentParser(description="WebSocket Server Example")
    parser.add_argument("--port", type=int, default=8000, help="Port to listen on")
    parser.add_argument("--root", default="./ws_root", help="Web root directory")
    args = parser.parse_args()

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    # Create web root if it doesn't exist
    web_root = Path(args.root)
    web_root.mkdir(exist_ok=True)

    # Create a simple test page if it doesn't exist
    index_file = web_root / "index.html"
    if not index_file.exists():
        index_file.write_text("""<!DOCTYPE html>
<html>
<head>
    <title>WebSocket Echo Server</title>
    <style>
        body { font-family: Arial, sans-serif; max-width: 800px; margin: 50px auto; padding: 20px; }
        #messages { border: 1px solid #ccc; height: 300px; overflow-y: scroll;
                    padding: 10px; margin: 10px 0; }
        #messageInput { width: 70%; padding: 5px; }
        button { padding: 5px 15px; }
        .sent { color: blue; }
        .received { color: green; }
    </style>
</head>
<body>
    <h1>WebSocket Echo Server</h1>
    <div id="status">Status: <span id="statusText">Disconnected</span></div>

    <div id="messages"></div>

    <input type="text" id="messageInput" placeholder="Type a message...">
    <button onclick="sendMessage()">Send</button>
    <button onclick="disconnect()">Disconnect</button>

    <h2>API Endpoints</h2>
    <ul>
        <li><a href="/api/stats">/api/stats</a> - Get server statistics</li>
        <li>POST /api/broadcast - Broadcast to all clients</li>
    </ul>

    <script>
        let ws;
        const messages = document.getElementById('messages');
        const statusText = document.getElementById('statusText');
        const messageInput = document.getElementById('messageInput');

        function connect() {
            ws = new WebSocket('ws://' + window.location.host + '/ws');

            ws.onopen = () => {
                statusText.textContent = 'Connected';
                statusText.style.color = 'green';
                addMessage('Connected to server', 'system');
            };

            ws.onmessage = (event) => {
                addMessage(event.data, 'received');
            };

            ws.onclose = () => {
                statusText.textContent = 'Disconnected';
                statusText.style.color = 'red';
                addMessage('Disconnected from server', 'system');
            };

            ws.onerror = (error) => {
                addMessage('Error: ' + error, 'error');
            };
        }

        function sendMessage() {
            const message = messageInput.value;
            if (message && ws && ws.readyState === WebSocket.OPEN) {
                ws.send(message);
                addMessage(message, 'sent');
                messageInput.value = '';
            }
        }

        function disconnect() {
            if (ws) {
                ws.close();
            }
        }

        function addMessage(text, type) {
            const div = document.createElement('div');
            div.className = type;
            div.textContent = text;
            messages.appendChild(div);
            messages.scrollTop = messages.scrollHeight;
        }

        messageInput.addEventListener('keypress', (e) => {
            if (e.key === 'Enter') {
                sendMessage();
            }
        });

        // Connect on page load
        connect();
    </script>
</body>
</html>""")

    # Start server
    mgr = Manager(handler)
    mgr.listen(f"http://0.0.0.0:{args.port}", http=True)

    print(f"WebSocket server started on http://localhost:{args.port}")
    print(f"WebSocket endpoint: ws://localhost:{args.port}/ws")
    print(f"Web root: {web_root.absolute()}")
    print(f"Try: Open http://localhost:{args.port}/ in your browser")
    print("Press Ctrl+C to stop")

    try:
        while not shutdown_requested:
            mgr.poll(100)
        print(f"\nShutting down... ({len(ws_clients)} clients connected)")
    finally:
        ws_clients.clear()
        mgr.close()
        print("Server stopped cleanly")


if __name__ == "__main__":
    main()
