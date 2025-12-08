Quickstart Guide
================

This guide will help you create your first cymongoose application in just a few minutes.

Basic HTTP Server
-----------------

Let's create a simple HTTP server that responds to requests:

.. code-block:: python

    import signal
    from cymongoose import Manager, MG_EV_HTTP_MSG

    shutdown_requested = False

    def signal_handler(sig, frame):
        """Handle Ctrl+C gracefully."""
        global shutdown_requested
        shutdown_requested = True

    def handler(conn, ev, data):
        """Event handler for HTTP requests."""
        if ev == MG_EV_HTTP_MSG:
            # data is an HttpMessage object
            print(f"{data.method} {data.uri}")

            # Send JSON response
            conn.reply(200, b'{"status": "ok", "message": "Hello World"}',
                      headers={"Content-Type": "application/json"})
            conn.drain()  # Graceful close

    def main():
        global shutdown_requested

        # Register signal handlers for Ctrl+C
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)

        # Create manager and listen on port 8000
        manager = Manager(handler)
        manager.listen('http://0.0.0.0:8000', http=True)

        print("Server running on http://0.0.0.0:8000")
        print("Press Ctrl+C to stop")

        try:
            # Event loop with 100ms timeout
            while not shutdown_requested:
                manager.poll(100)
            print("Shutting down...")
        finally:
            manager.close()
            print("Server stopped")

    if __name__ == "__main__":
        main()

Save this as ``server.py`` and run:

.. code-block:: bash

    python server.py

Test it:

.. code-block:: bash

    curl http://localhost:8000
    # Output: {"status": "ok", "message": "Hello World"}

Understanding the Code
~~~~~~~~~~~~~~~~~~~~~~

1. **Signal Handler**: Uses signal handlers instead of try/except for Ctrl+C. This is required because ``poll()`` releases the GIL for performance.

2. **Event Handler**: The ``handler()`` function receives:

   - ``conn``: :class:`~cymongoose.Connection` object
   - ``ev``: Event type constant (``MG_EV_HTTP_MSG``, etc.)
   - ``data``: Event-specific data (``HttpMessage`` for HTTP events)

3. **Manager**: The :class:`~cymongoose.Manager` manages the event loop.

4. **Graceful Shutdown**: ``conn.drain()`` ensures the response is sent before closing.

Routing Requests
----------------

Handle different URL paths:

.. code-block:: python

    def handler(conn, ev, data):
        if ev == MG_EV_HTTP_MSG:
            uri = data.uri

            if uri == "/":
                conn.reply(200, b'{"message": "Home page"}')
            elif uri == "/api/status":
                conn.reply(200, b'{"status": "running"}')
            elif uri.startswith("/api/user/"):
                user_id = uri.split("/")[-1]
                conn.reply(200, f'{{"user_id": "{user_id}"}}'.encode())
            else:
                conn.reply(404, b'{"error": "Not found"}')

            conn.drain()

Request Data
------------

Access request details:

.. code-block:: python

    def handler(conn, ev, data):
        if ev == MG_EV_HTTP_MSG:
            # HTTP method
            print(f"Method: {data.method}")  # GET, POST, etc.

            # Request URI
            print(f"URI: {data.uri}")  # /api/users

            # Query string
            print(f"Query: {data.query}")  # id=123&name=foo
            param = data.query_var("id")  # Get specific parameter

            # Headers
            content_type = data.header("Content-Type")
            for name, value in data.headers():
                print(f"{name}: {value}")

            # Body
            body_bytes = data.body_bytes  # Raw bytes
            body_text = data.body_text    # UTF-8 decoded

            conn.reply(200, b"OK")
            conn.drain()

Static File Server
------------------

Serve static files from a directory:

.. code-block:: python

    from cymongoose import Manager, MG_EV_HTTP_MSG

    def handler(conn, ev, data):
        if ev == MG_EV_HTTP_MSG:
            # Serve files from ./public directory
            conn.serve_dir(data, "./public")

    manager = Manager(handler)
    manager.listen('http://0.0.0.0:8000', http=True)

    # ... poll loop

Directory structure:

.. code-block:: text

    public/
    ├── index.html
    ├── styles.css
    └── app.js

WebSocket Echo Server
---------------------

Upgrade HTTP to WebSocket and echo messages:

.. code-block:: python

    from cymongoose import (
        Manager,
        MG_EV_HTTP_MSG,
        MG_EV_WS_MSG,
        WEBSOCKET_OP_TEXT,
    )

    def handler(conn, ev, data):
        if ev == MG_EV_HTTP_MSG:
            # Upgrade to WebSocket
            if data.uri == "/ws":
                conn.ws_upgrade(data)
            else:
                conn.reply(200, b"Use /ws for WebSocket")
                conn.drain()

        elif ev == MG_EV_WS_MSG:
            # Echo message back
            print(f"Received: {data.text}")
            conn.ws_send(f"Echo: {data.text}", WEBSOCKET_OP_TEXT)

Test with a WebSocket client:

.. code-block:: python

    # client.py
    import websocket

    ws = websocket.WebSocket()
    ws.connect("ws://localhost:8000/ws")
    ws.send("Hello WebSocket!")
    print(ws.recv())  # Echo: Hello WebSocket!
    ws.close()

HTTP Client
-----------

Make HTTP requests:

.. code-block:: python

    from cymongoose import Manager, MG_EV_CONNECT, MG_EV_HTTP_MSG
    import signal

    shutdown_requested = False

    def signal_handler(sig, frame):
        global shutdown_requested
        shutdown_requested = True

    def handler(conn, ev, data):
        if ev == MG_EV_CONNECT:
            # Connected - send request
            conn.send(b"GET / HTTP/1.1\\r\\nHost: example.com\\r\\n\\r\\n")

        elif ev == MG_EV_HTTP_MSG:
            # Response received
            print(f"Status: {data.status()}")
            print(f"Body: {data.body_text[:100]}...")
            conn.close()
            global shutdown_requested
            shutdown_requested = True

    signal.signal(signal.SIGINT, signal_handler)

    manager = Manager(handler)
    manager.connect("http://example.com:80", http=True)

    while not shutdown_requested:
        manager.poll(100)

    manager.close()

MQTT Publish/Subscribe
----------------------

Connect to MQTT broker and subscribe to topics:

.. code-block:: python

    from cymongoose import (
        Manager,
        MG_EV_MQTT_OPEN,
        MG_EV_MQTT_MSG,
    )

    def handler(conn, ev, data):
        if ev == MG_EV_MQTT_OPEN:
            # Connected to broker
            print(f"Connected, status={data}")
            conn.mqtt_sub("test/topic", qos=1)

        elif ev == MG_EV_MQTT_MSG:
            # Message received
            print(f"Topic: {data.topic}")
            print(f"Message: {data.text}")

            # Publish response
            conn.mqtt_pub("test/response", "Got it!", qos=1)

    manager = Manager(handler)
    manager.mqtt_connect(
        "mqtt://broker.hivemq.com:1883",
        client_id="cymongoose-client",
        clean_session=True,
        keepalive=60,
    )

    # ... poll loop

HTTPS Server with TLS
---------------------

Create an HTTPS server with self-signed certificates:

.. code-block:: python

    from cymongoose import Manager, MG_EV_HTTP_MSG, MG_EV_ACCEPT, TlsOpts

    # Load certificates
    cert = open("server.crt", "rb").read()
    key = open("server.key", "rb").read()

    def handler(conn, ev, data):
        if ev == MG_EV_ACCEPT:
            # Initialize TLS on new connections
            opts = TlsOpts(cert=cert, key=key)
            conn.tls_init(opts)

        elif ev == MG_EV_HTTP_MSG:
            conn.reply(200, b"Secure Hello!")
            conn.drain()

    manager = Manager(handler)
    manager.listen('https://0.0.0.0:8443', http=True)

    # ... poll loop

Generate self-signed cert for testing:

.. code-block:: bash

    openssl req -x509 -newkey rsa:2048 -keyout server.key \\
        -out server.crt -days 365 -nodes

Next Steps
----------

Now that you've built your first cymongoose application, explore:

- :doc:`examples` - More complete examples for all protocols
- :doc:`guide/index` - In-depth protocol guides
- :doc:`api/index` - Full API reference
- :doc:`advanced/performance` - Performance optimization tips
