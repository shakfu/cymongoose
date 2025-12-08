Examples
========

This page contains complete, runnable examples for common use cases. All examples include proper signal handling for production use.

Basic Examples
--------------

Simple JSON API Server
~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: python

    """Simple REST API with JSON responses."""
    import signal
    import json
    from cymongoose import Manager, MG_EV_HTTP_MSG

    shutdown_requested = False

    def signal_handler(sig, frame):
        global shutdown_requested
        shutdown_requested = True

    # In-memory database
    users = {
        "1": {"id": "1", "name": "Alice", "email": "alice@example.com"},
        "2": {"id": "2", "name": "Bob", "email": "bob@example.com"},
    }

    def handler(conn, ev, data):
        if ev == MG_EV_HTTP_MSG:
            method = data.method
            uri = data.uri

            # GET /api/users - List all users
            if method == "GET" and uri == "/api/users":
                response = json.dumps(list(users.values())).encode()
                conn.reply(200, response,
                          headers={"Content-Type": "application/json"})

            # GET /api/users/{id} - Get specific user
            elif method == "GET" and uri.startswith("/api/users/"):
                user_id = uri.split("/")[-1]
                if user_id in users:
                    response = json.dumps(users[user_id]).encode()
                    conn.reply(200, response,
                              headers={"Content-Type": "application/json"})
                else:
                    conn.reply(404, b'{"error": "User not found"}',
                              headers={"Content-Type": "application/json"})

            # POST /api/users - Create user
            elif method == "POST" and uri == "/api/users":
                try:
                    new_user = json.loads(data.body_text)
                    user_id = str(len(users) + 1)
                    new_user["id"] = user_id
                    users[user_id] = new_user
                    response = json.dumps(new_user).encode()
                    conn.reply(201, response,
                              headers={"Content-Type": "application/json"})
                except json.JSONDecodeError:
                    conn.reply(400, b'{"error": "Invalid JSON"}',
                              headers={"Content-Type": "application/json"})

            else:
                conn.reply(404, b'{"error": "Not found"}',
                          headers={"Content-Type": "application/json"})

            conn.drain()

    def main():
        global shutdown_requested
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)

        manager = Manager(handler)
        manager.listen('http://0.0.0.0:8000', http=True)

        print("JSON API server running on http://0.0.0.0:8000")
        print("Try: curl http://localhost:8000/api/users")

        try:
            while not shutdown_requested:
                manager.poll(100)
            print("Shutting down...")
        finally:
            manager.close()

    if __name__ == "__main__":
        main()

File Upload Server
~~~~~~~~~~~~~~~~~~

.. code-block:: python

    """HTTP server with file upload support."""
    import signal
    import os
    from cymongoose import Manager, MG_EV_HTTP_MSG, http_parse_multipart

    shutdown_requested = False

    def signal_handler(sig, frame):
        global shutdown_requested
        shutdown_requested = True

    def handler(conn, ev, data):
        if ev == MG_EV_HTTP_MSG:
            if data.method == "POST" and data.uri == "/upload":
                # Parse multipart form data
                offset = 0
                while True:
                    offset, part = http_parse_multipart(data.body_bytes, offset)
                    if part is None:
                        break

                    filename = part['filename']
                    if filename:
                        # Save uploaded file
                        filepath = os.path.join("uploads", filename)
                        os.makedirs("uploads", exist_ok=True)
                        with open(filepath, "wb") as f:
                            f.write(part['body'])
                        print(f"Saved: {filepath}")

                conn.reply(200, b'{"status": "uploaded"}',
                          headers={"Content-Type": "application/json"})
            else:
                # Serve upload form
                html = b"""
                <html>
                <body>
                    <h1>File Upload</h1>
                    <form method="POST" action="/upload" enctype="multipart/form-data">
                        <input type="file" name="file">
                        <button type="submit">Upload</button>
                    </form>
                </body>
                </html>
                """
                conn.reply(200, html,
                          headers={"Content-Type": "text/html"})
            conn.drain()

    # ... main() function similar to previous examples

Server-Sent Events (SSE)
~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: python

    """Real-time updates using Server-Sent Events."""
    import signal
    import time
    from cymongoose import Manager, MG_EV_HTTP_MSG

    shutdown_requested = False

    def signal_handler(sig, frame):
        global shutdown_requested
        shutdown_requested = True

    # Track SSE connections
    sse_connections = []

    def handler(conn, ev, data):
        if ev == MG_EV_HTTP_MSG:
            if data.uri == "/events":
                # Start SSE stream
                conn.reply(200, "",
                          headers={
                              "Content-Type": "text/event-stream",
                              "Cache-Control": "no-cache",
                              "Connection": "keep-alive"
                          })
                sse_connections.append(conn)
                print(f"SSE client connected: {len(sse_connections)} total")

            else:
                # Serve test page
                html = b"""
                <html>
                <body>
                    <h1>Server-Sent Events Demo</h1>
                    <div id="events"></div>
                    <script>
                        const events = new EventSource('/events');
                        events.addEventListener('update', e => {
                            document.getElementById('events').innerHTML +=
                                '<p>' + e.data + '</p>';
                        });
                    </script>
                </body>
                </html>
                """
                conn.reply(200, html,
                          headers={"Content-Type": "text/html"})
                conn.drain()

    def broadcast_updates():
        """Send updates to all SSE clients."""
        import random
        data = f"Update at {time.strftime('%H:%M:%S')} - Value: {random.randint(1, 100)}"

        for conn in sse_connections[:]:  # Copy list to avoid modification during iteration
            try:
                conn.http_sse("update", data)
            except RuntimeError:
                # Connection closed
                sse_connections.remove(conn)

    def main():
        global shutdown_requested
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)

        manager = Manager(handler)
        manager.listen('http://0.0.0.0:8000', http=True)

        # Timer to broadcast updates every 2 seconds
        manager.timer_add(2000, broadcast_updates, repeat=True)

        print("SSE server running on http://0.0.0.0:8000")

        try:
            while not shutdown_requested:
                manager.poll(100)
        finally:
            manager.close()

    if __name__ == "__main__":
        main()

WebSocket Examples
------------------

Chat Room Server
~~~~~~~~~~~~~~~~

.. code-block:: python

    """WebSocket-based chat room."""
    import signal
    from cymongoose import (
        Manager,
        MG_EV_HTTP_MSG,
        MG_EV_WS_MSG,
        MG_EV_CLOSE,
        WEBSOCKET_OP_TEXT,
    )

    shutdown_requested = False
    clients = []

    def signal_handler(sig, frame):
        global shutdown_requested
        shutdown_requested = True

    def broadcast(message, exclude=None):
        """Send message to all clients except excluded one."""
        for client in clients[:]:
            if client != exclude:
                try:
                    client.ws_send(message, WEBSOCKET_OP_TEXT)
                except RuntimeError:
                    clients.remove(client)

    def handler(conn, ev, data):
        if ev == MG_EV_HTTP_MSG:
            if data.uri == "/ws":
                conn.ws_upgrade(data)
                clients.append(conn)
                conn.userdata = {"name": f"User{len(clients)}"}
                broadcast(f"{conn.userdata['name']} joined", exclude=conn)
                print(f"Client connected: {len(clients)} total")
            else:
                # Serve chat interface
                html = b"""
                <html><body>
                    <div id="messages" style="height:400px;overflow:auto;border:1px solid"></div>
                    <input id="input" type="text" style="width:300px">
                    <button onclick="send()">Send</button>
                    <script>
                        const ws = new WebSocket('ws://' + location.host + '/ws');
                        ws.onmessage = e => {
                            document.getElementById('messages').innerHTML +=
                                '<div>' + e.data + '</div>';
                        };
                        function send() {
                            const msg = document.getElementById('input').value;
                            ws.send(msg);
                            document.getElementById('input').value = '';
                        }
                        document.getElementById('input').onkeypress = e => {
                            if (e.key === 'Enter') send();
                        };
                    </script>
                </body></html>
                """
                conn.reply(200, html,
                          headers={"Content-Type": "text/html"})
                conn.drain()

        elif ev == MG_EV_WS_MSG:
            # Broadcast message to all clients
            message = f"{conn.userdata['name']}: {data.text}"
            broadcast(message)

        elif ev == MG_EV_CLOSE:
            if conn in clients:
                clients.remove(conn)
                broadcast(f"{conn.userdata.get('name', 'User')} left")
                print(f"Client disconnected: {len(clients)} remaining")

    # ... main() function

MQTT Examples
-------------

Temperature Monitor
~~~~~~~~~~~~~~~~~~~

.. code-block:: python

    """MQTT temperature monitoring system."""
    import signal
    import random
    import time
    from cymongoose import (
        Manager,
        MG_EV_MQTT_OPEN,
        MG_EV_MQTT_MSG,
    )

    shutdown_requested = False

    def signal_handler(sig, frame):
        global shutdown_requested
        shutdown_requested = True

    def handler(conn, ev, data):
        if ev == MG_EV_MQTT_OPEN:
            print(f"Connected to broker, status={data}")
            # Subscribe to temperature sensors
            conn.mqtt_sub("sensors/+/temperature", qos=1)
            conn.mqtt_sub("sensors/+/humidity", qos=1)

        elif ev == MG_EV_MQTT_MSG:
            topic = data.topic
            value = data.text

            print(f"{topic}: {value}")

            # Trigger alert if temperature too high
            if "temperature" in topic and float(value) > 30:
                alert = f"HIGH TEMP ALERT: {value}°C on {topic}"
                conn.mqtt_pub("alerts/temperature", alert, qos=1)

    def publish_readings(conn):
        """Publish simulated sensor readings."""
        sensors = ["sensor1", "sensor2", "sensor3"]

        for sensor in sensors:
            temp = random.uniform(20, 35)
            humidity = random.uniform(40, 80)

            conn.mqtt_pub(f"sensors/{sensor}/temperature",
                         f"{temp:.1f}", qos=1)
            conn.mqtt_pub(f"sensors/{sensor}/humidity",
                         f"{humidity:.1f}", qos=1)

    def main():
        global shutdown_requested
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)

        manager = Manager(handler)
        conn = manager.mqtt_connect(
            "mqtt://broker.hivemq.com:1883",
            client_id="temp-monitor",
            clean_session=True,
            keepalive=60,
        )

        # Publish readings every 5 seconds
        manager.timer_add(5000, lambda: publish_readings(conn), repeat=True)

        print("MQTT temperature monitor started")

        try:
            while not shutdown_requested:
                manager.poll(100)
        finally:
            manager.close()

    if __name__ == "__main__":
        main()

Advanced Examples
-----------------

Multi-threaded Request Handler
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

See :doc:`advanced/threading` for complete example of offloading work to background threads.

HTTPS Reverse Proxy
~~~~~~~~~~~~~~~~~~~

See ``tests/examples/advanced/http_proxy_client.py`` for a complete HTTP proxy implementation.

TLS/HTTPS Server
~~~~~~~~~~~~~~~~

See ``tests/examples/advanced/tls_https_server.py`` for production TLS configuration.

More Examples
-------------

The ``tests/examples/`` directory contains 17 complete, tested examples covering all protocols:

- **HTTP**: Server, client, streaming, file upload, RESTful API, SSE
- **WebSocket**: Server, broadcasting
- **MQTT**: Client, server/broker
- **Network**: TCP echo, UDP echo, DNS resolution, SNTP time sync
- **Advanced**: TLS/HTTPS, HTTP proxy, multi-threading

All examples are runnable and include comprehensive tests:

.. code-block:: bash

    # Run HTTP server example
    python tests/examples/http/http_server.py

    # Run WebSocket chat
    python tests/examples/websocket/websocket_server.py

    # Run MQTT client
    python tests/examples/mqtt/mqtt_client.py

See Also
--------

- :doc:`quickstart` - Basic tutorial
- :doc:`guide/index` - Protocol guides
- :doc:`api/index` - API reference
