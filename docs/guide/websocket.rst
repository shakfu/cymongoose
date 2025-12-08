WebSocket Guide
===============

This guide covers WebSocket communication using cymongoose.

WebSocket Server
----------------

Basic WebSocket Server
~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: python

    from cymongoose import (
        Manager,
        MG_EV_HTTP_MSG,
        MG_EV_WS_MSG,
        MG_EV_CLOSE,
        WEBSOCKET_OP_TEXT,
    )

    clients = []

    def handler(conn, ev, data):
        if ev == MG_EV_HTTP_MSG:
            if data.uri == "/ws":
                # Upgrade HTTP to WebSocket
                conn.ws_upgrade(data)
                clients.append(conn)
                print(f"Client connected: {len(clients)} total")

        elif ev == MG_EV_WS_MSG:
            # Echo message back
            print(f"Received: {data.text}")
            conn.ws_send(f"Echo: {data.text}", WEBSOCKET_OP_TEXT)

        elif ev == MG_EV_CLOSE:
            if conn in clients:
                clients.remove(conn)
                print(f"Client disconnected: {len(clients)} remaining")

Mixed HTTP/WebSocket Server
~~~~~~~~~~~~~~~~~~~~~~~~~~~

Serve both HTTP and WebSocket on same port:

.. code-block:: python

    def handler(conn, ev, data):
        if ev == MG_EV_HTTP_MSG:
            if data.uri == "/ws":
                conn.ws_upgrade(data)
            elif data.uri == "/":
                # Serve WebSocket client page
                html = b"""
                <html><body>
                    <script>
                        const ws = new WebSocket('ws://' + location.host + '/ws');
                        ws.onmessage = e => console.log(e.data);
                        ws.onopen = () => ws.send('Hello!');
                    </script>
                </body></html>
                """
                conn.reply(200, html, headers={"Content-Type": "text/html"})
                conn.drain()
            else:
                conn.reply(404, b"Not Found")
                conn.drain()

Sending Messages
----------------

Text Messages
~~~~~~~~~~~~~

.. code-block:: python

    from cymongoose import WEBSOCKET_OP_TEXT

    # Send UTF-8 text
    conn.ws_send("Hello, WebSocket!", WEBSOCKET_OP_TEXT)

    # Send JSON
    import json
    data = {"type": "update", "value": 42}
    conn.ws_send(json.dumps(data), WEBSOCKET_OP_TEXT)

Binary Messages
~~~~~~~~~~~~~~~

.. code-block:: python

    from cymongoose import WEBSOCKET_OP_BINARY

    # Send binary data
    binary_data = bytes([0x00, 0x01, 0x02, 0xFF])
    conn.ws_send(binary_data, WEBSOCKET_OP_BINARY)

Broadcasting
~~~~~~~~~~~~

Send to all connected clients:

.. code-block:: python

    def broadcast(message, exclude=None):
        """Broadcast to all clients except excluded one."""
        for client in clients[:]:  # Copy to avoid modification during iteration
            if client != exclude:
                try:
                    client.ws_send(message, WEBSOCKET_OP_TEXT)
                except RuntimeError:
                    # Connection closed
                    clients.remove(client)

    # Use in handler
    def handler(conn, ev, data):
        if ev == MG_EV_WS_MSG:
            # Broadcast to all except sender
            broadcast(f"User says: {data.text}", exclude=conn)

Receiving Messages
------------------

Text vs Binary
~~~~~~~~~~~~~~

.. code-block:: python

    from cymongoose import (
        MG_EV_WS_MSG,
        WEBSOCKET_OP_TEXT,
        WEBSOCKET_OP_BINARY,
    )

    def handler(conn, ev, data):
        if ev == MG_EV_WS_MSG:
            if data.flags == WEBSOCKET_OP_TEXT:
                # Text message
                text = data.text
                print(f"Text: {text}")

            elif data.flags == WEBSOCKET_OP_BINARY:
                # Binary message
                binary = data.data
                print(f"Binary: {len(binary)} bytes")

JSON Messages
~~~~~~~~~~~~~

.. code-block:: python

    import json

    def handler(conn, ev, data):
        if ev == MG_EV_WS_MSG:
            try:
                msg = json.loads(data.text)
                msg_type = msg.get("type")

                if msg_type == "chat":
                    handle_chat(conn, msg)
                elif msg_type == "ping":
                    conn.ws_send('{"type": "pong"}', WEBSOCKET_OP_TEXT)

            except json.JSONDecodeError:
                print("Invalid JSON")

Connection State
----------------

Track Client Information
~~~~~~~~~~~~~~~~~~~~~~~~

Use ``conn.userdata`` to store per-client state:

.. code-block:: python

    def handler(conn, ev, data):
        if ev == MG_EV_HTTP_MSG and data.uri == "/ws":
            conn.ws_upgrade(data)

            # Initialize client state
            conn.userdata = {
                "username": None,
                "joined_at": time.time(),
                "room": "lobby",
            }

        elif ev == MG_EV_WS_MSG:
            # Access client state
            username = conn.userdata.get("username", "Anonymous")
            broadcast(f"{username}: {data.text}")

Chat Room Example
-----------------

Complete chat room implementation:

.. code-block:: python

    from cymongoose import (
        Manager,
        MG_EV_HTTP_MSG,
        MG_EV_WS_MSG,
        MG_EV_CLOSE,
        WEBSOCKET_OP_TEXT,
    )
    import json
    import time

    clients = []

    def broadcast(message_data, exclude=None):
        msg = json.dumps(message_data)
        for client in clients[:]:
            if client != exclude:
                try:
                    client.ws_send(msg, WEBSOCKET_OP_TEXT)
                except RuntimeError:
                    clients.remove(client)

    def handler(conn, ev, data):
        if ev == MG_EV_HTTP_MSG:
            if data.uri == "/ws":
                conn.ws_upgrade(data)
                clients.append(conn)

                # Initialize user
                conn.userdata = {
                    "username": f"User{len(clients)}",
                    "joined_at": time.time(),
                }

                # Notify others
                broadcast({
                    "type": "join",
                    "username": conn.userdata["username"],
                    "count": len(clients),
                })

        elif ev == MG_EV_WS_MSG:
            try:
                msg = json.loads(data.text)

                if msg["type"] == "message":
                    # Broadcast chat message
                    broadcast({
                        "type": "message",
                        "username": conn.userdata["username"],
                        "text": msg["text"],
                        "timestamp": time.time(),
                    })

                elif msg["type"] == "setname":
                    # Change username
                    old_name = conn.userdata["username"]
                    new_name = msg["username"]
                    conn.userdata["username"] = new_name

                    broadcast({
                        "type": "rename",
                        "old": old_name,
                        "new": new_name,
                    })

            except (json.JSONDecodeError, KeyError):
                conn.ws_send('{"error": "Invalid message"}', WEBSOCKET_OP_TEXT)

        elif ev == MG_EV_CLOSE:
            if conn in clients:
                clients.remove(conn)
                broadcast({
                    "type": "leave",
                    "username": conn.userdata.get("username", "Unknown"),
                    "count": len(clients),
                })

WebSocket Client
----------------

Python WebSocket Client
~~~~~~~~~~~~~~~~~~~~~~~

Using websocket-client library:

.. code-block:: python

    import websocket

    ws = websocket.WebSocket()
    ws.connect("ws://localhost:8000/ws")

    # Send message
    ws.send("Hello, Server!")

    # Receive message
    message = ws.recv()
    print(f"Received: {message}")

    ws.close()

JavaScript WebSocket Client
~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: html

    <script>
        const ws = new WebSocket('ws://localhost:8000/ws');

        ws.onopen = () => {
            console.log('Connected');
            ws.send(JSON.stringify({type: 'message', text: 'Hello!'}));
        };

        ws.onmessage = (event) => {
            const data = JSON.parse(event.data);
            console.log('Received:', data);
        };

        ws.onclose = () => {
            console.log('Disconnected');
        };

        ws.onerror = (error) => {
            console.error('WebSocket error:', error);
        };
    </script>

Secure WebSocket (WSS)
----------------------

.. code-block:: python

    from cymongoose import MG_EV_ACCEPT, TlsOpts

    cert = open("server.crt", "rb").read()
    key = open("server.key", "rb").read()

    def handler(conn, ev, data):
        if ev == MG_EV_ACCEPT:
            # Initialize TLS
            opts = TlsOpts(cert=cert, key=key)
            conn.tls_init(opts)

        elif ev == MG_EV_HTTP_MSG and data.uri == "/ws":
            # Upgrade to secure WebSocket
            conn.ws_upgrade(data)

    manager = Manager(handler)
    manager.listen('https://0.0.0.0:8443', http=True)

Client connects with wss://

.. code-block:: javascript

    const ws = new WebSocket('wss://localhost:8443/ws');

Best Practices
--------------

1. **Always track clients** in a list for broadcasting
2. **Copy client list** before iterating (``clients[:]``)
3. **Handle closed connections** with try/except
4. **Use JSON** for structured messages
5. **Validate message format** before processing
6. **Set user state** with ``conn.userdata``
7. **Clean up** on ``MG_EV_CLOSE``

See Also
--------

- :doc:`http` - HTTP/HTTPS guide
- :doc:`tls` - Secure WebSocket (WSS)
- :doc:`../examples` - Complete chat room example
- :doc:`../api/connection` - Connection API
