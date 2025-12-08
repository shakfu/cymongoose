Connection Class
================

.. currentmodule:: cymongoose

.. autoclass:: Connection
   :members:
   :undoc-members:
   :member-order: bysource

Overview
--------

The :class:`Connection` class represents a single network connection. Connections are created by :class:`Manager` and passed to event handlers.

**Important**: Do not create Connection objects directly. They are created automatically by the Manager.

Connection Lifecycle
--------------------

.. code-block:: python

    def handler(conn, ev, data):
        if ev == MG_EV_ACCEPT:
            # New inbound connection
            print(f"Client connected from {conn.remote_addr}")

        elif ev == MG_EV_CONNECT:
            # Outbound connection established
            print(f"Connected to {conn.remote_addr}")

        elif ev == MG_EV_CLOSE:
            # Connection closing
            print(f"Connection {conn.id} closed")
            # conn object becomes invalid after this event

Connection Properties
---------------------

Basic Information
~~~~~~~~~~~~~~~~~

.. autoattribute:: Connection.id
.. autoattribute:: Connection.handler
.. autoattribute:: Connection.userdata

State Flags
~~~~~~~~~~~

.. autoattribute:: Connection.is_listening
.. autoattribute:: Connection.is_client
.. autoattribute:: Connection.is_tls
.. autoattribute:: Connection.is_udp
.. autoattribute:: Connection.is_websocket
.. autoattribute:: Connection.is_readable
.. autoattribute:: Connection.is_writable
.. autoattribute:: Connection.is_closing
.. autoattribute:: Connection.is_full
.. autoattribute:: Connection.is_draining

Addresses
~~~~~~~~~

.. autoattribute:: Connection.local_addr
.. autoattribute:: Connection.remote_addr

Example:

.. code-block:: python

    local_ip, local_port, is_ipv6 = conn.local_addr
    remote_ip, remote_port, is_ipv6 = conn.remote_addr

    print(f"Local: {local_ip}:{local_port}")
    print(f"Remote: {remote_ip}:{remote_port}")

Buffer Management
~~~~~~~~~~~~~~~~~

.. autoattribute:: Connection.recv_len
.. autoattribute:: Connection.send_len
.. autoattribute:: Connection.recv_size
.. autoattribute:: Connection.send_size

Flow control example:

.. code-block:: python

    def handler(conn, ev, data):
        if ev == MG_EV_READ:
            if conn.recv_len > 100000:  # 100KB
                print("Large amount of data buffered")

            if conn.is_full:
                print("Receive buffer full - backpressure active")

        if ev == MG_EV_WRITE:
            if conn.send_len > 0:
                print(f"Still sending {conn.send_len} bytes")

Sending Data
------------

Raw Data
~~~~~~~~

.. automethod:: Connection.send

Example:

.. code-block:: python

    # Send bytes
    conn.send(b"Hello, World!")

    # Send string (auto-encoded to UTF-8)
    conn.send("Hello, World!")

HTTP Responses
~~~~~~~~~~~~~~

.. automethod:: Connection.reply

Example:

.. code-block:: python

    # Simple response
    conn.reply(200, b"OK")

    # JSON response
    import json
    data = {"status": "ok", "count": 42}
    conn.reply(200, json.dumps(data).encode(),
              headers={"Content-Type": "application/json"})

    # HTML response
    conn.reply(200, b"<html><body>Hello</body></html>",
              headers={"Content-Type": "text/html"})

Static Files
~~~~~~~~~~~~

.. automethod:: Connection.serve_dir
.. automethod:: Connection.serve_file

Example:

.. code-block:: python

    def handler(conn, ev, data):
        if ev == MG_EV_HTTP_MSG:
            if data.uri.startswith("/static/"):
                # Serve static files
                conn.serve_dir(data, "./public")
            elif data.uri == "/favicon.ico":
                # Serve single file
                conn.serve_file(data, "./public/favicon.ico")
            else:
                # Dynamic response
                conn.reply(200, b"Hello!")
                conn.drain()

HTTP Streaming
~~~~~~~~~~~~~~

.. automethod:: Connection.http_chunk

Example:

.. code-block:: python

    def handler(conn, ev, data):
        if ev == MG_EV_HTTP_MSG:
            # Start chunked response
            conn.reply(200, "",
                      headers={"Transfer-Encoding": "chunked"})

            # Send chunks
            conn.http_chunk("First chunk\\n")
            conn.http_chunk("Second chunk\\n")
            conn.http_chunk("Third chunk\\n")

            # End chunked encoding
            conn.http_chunk("")  # Empty chunk signals end

Server-Sent Events
~~~~~~~~~~~~~~~~~~

.. automethod:: Connection.http_sse

Example:

.. code-block:: python

    def handler(conn, ev, data):
        if ev == MG_EV_HTTP_MSG and data.uri == "/events":
            # Start SSE stream
            conn.reply(200, "",
                      headers={
                          "Content-Type": "text/event-stream",
                          "Cache-Control": "no-cache",
                      })

            # Send events
            conn.http_sse("message", "Hello from server")
            conn.http_sse("update", json.dumps({"value": 42}))

WebSocket
---------

Upgrade
~~~~~~~

.. automethod:: Connection.ws_upgrade

Send Messages
~~~~~~~~~~~~~

.. automethod:: Connection.ws_send

Example:

.. code-block:: python

    from cymongoose import (
        MG_EV_HTTP_MSG,
        MG_EV_WS_MSG,
        WEBSOCKET_OP_TEXT,
        WEBSOCKET_OP_BINARY,
    )

    def handler(conn, ev, data):
        if ev == MG_EV_HTTP_MSG:
            if data.uri == "/ws":
                # Upgrade to WebSocket
                conn.ws_upgrade(data)

        elif ev == MG_EV_WS_MSG:
            # Echo message back
            if data.flags == WEBSOCKET_OP_TEXT:
                conn.ws_send(f"Echo: {data.text}", WEBSOCKET_OP_TEXT)
            else:
                conn.ws_send(data.data, WEBSOCKET_OP_BINARY)

MQTT
----

Publish
~~~~~~~

.. automethod:: Connection.mqtt_pub

Subscribe
~~~~~~~~~

.. automethod:: Connection.mqtt_sub

Other Operations
~~~~~~~~~~~~~~~~

.. automethod:: Connection.mqtt_ping
.. automethod:: Connection.mqtt_pong
.. automethod:: Connection.mqtt_disconnect

Example:

.. code-block:: python

    from cymongoose import MG_EV_MQTT_OPEN, MG_EV_MQTT_MSG

    def handler(conn, ev, data):
        if ev == MG_EV_MQTT_OPEN:
            # Connected to broker
            print("MQTT connected")

            # Subscribe to topics
            conn.mqtt_sub("sensors/+/temperature", qos=1)
            conn.mqtt_sub("sensors/+/humidity", qos=1)

        elif ev == MG_EV_MQTT_MSG:
            # Message received
            print(f"Topic: {data.topic}")
            print(f"Message: {data.text}")

            # Publish response
            conn.mqtt_pub("ack/received", "OK", qos=1, retain=False)

TLS/SSL
-------

Initialize TLS
~~~~~~~~~~~~~~

.. automethod:: Connection.tls_init

Free TLS
~~~~~~~~

.. automethod:: Connection.tls_free

Example:

.. code-block:: python

    from cymongoose import MG_EV_ACCEPT, TlsOpts

    # Load certificates
    cert = open("server.crt", "rb").read()
    key = open("server.key", "rb").read()
    ca = open("ca.crt", "rb").read()

    def handler(conn, ev, data):
        if ev == MG_EV_ACCEPT:
            # Initialize TLS on accepted connection
            opts = TlsOpts(cert=cert, key=key, ca=ca)
            conn.tls_init(opts)

        elif ev == MG_EV_TLS_HS:
            # TLS handshake complete
            print("TLS established")

DNS Resolution
--------------

.. automethod:: Connection.resolve
.. automethod:: Connection.resolve_cancel

Example:

.. code-block:: python

    from cymongoose import MG_EV_RESOLVE

    def handler(conn, ev, data):
        if ev == MG_EV_OPEN:
            # Start DNS resolution
            conn.resolve("example.com")

        elif ev == MG_EV_RESOLVE:
            # Resolution complete
            print(f"Resolved to: {conn.remote_addr}")

SNTP (Time Sync)
----------------

.. automethod:: Connection.sntp_request

Example:

.. code-block:: python

    from cymongoose import MG_EV_SNTP_TIME

    def handler(conn, ev, data):
        if ev == MG_EV_CONNECT:
            # Connected to SNTP server
            conn.sntp_request()

        elif ev == MG_EV_SNTP_TIME:
            # Time received (milliseconds since epoch)
            import datetime
            dt = datetime.datetime.fromtimestamp(data / 1000.0)
            print(f"Server time: {dt}")

Authentication
--------------

.. automethod:: Connection.http_basic_auth

Example:

.. code-block:: python

    from cymongoose import MG_EV_CONNECT

    def handler(conn, ev, data):
        if ev == MG_EV_CONNECT:
            # Send basic auth credentials
            conn.http_basic_auth("username", "password")
            conn.send(b"GET /protected HTTP/1.1\\r\\n\\r\\n")

Buffer Access
-------------

.. automethod:: Connection.recv_data
.. automethod:: Connection.send_data

Example:

.. code-block:: python

    from cymongoose import MG_EV_READ

    def handler(conn, ev, data):
        if ev == MG_EV_READ:
            # Peek at receive buffer
            data = conn.recv_data(100)  # First 100 bytes
            print(f"Received: {data}")

            # Check send buffer
            pending = conn.send_data()
            if len(pending) > 10000:
                print("Large amount of data pending")

Connection Management
---------------------

Per-Connection Handler
~~~~~~~~~~~~~~~~~~~~~~

.. automethod:: Connection.set_handler

Example:

.. code-block:: python

    def main_handler(conn, ev, data):
        if ev == MG_EV_HTTP_MSG:
            if data.uri == "/ws":
                # Switch to WebSocket handler
                conn.set_handler(websocket_handler)
                conn.ws_upgrade(data)

    def websocket_handler(conn, ev, data):
        if ev == MG_EV_WS_MSG:
            conn.ws_send(f"Echo: {data.text}")

User Data
~~~~~~~~~

Store custom data on connections:

.. code-block:: python

    def handler(conn, ev, data):
        if ev == MG_EV_ACCEPT:
            # Initialize user data
            conn.userdata = {
                "authenticated": False,
                "username": None,
                "connected_at": time.time(),
            }

        elif ev == MG_EV_HTTP_MSG:
            # Access user data
            if conn.userdata["authenticated"]:
                conn.reply(200, b"Welcome!")
            else:
                conn.reply(401, b"Unauthorized")

Closing Connections
~~~~~~~~~~~~~~~~~~~

.. automethod:: Connection.close
.. automethod:: Connection.drain

**Important**: Use ``drain()`` for graceful shutdown, not ``close()``.

Example:

.. code-block:: python

    def handler(conn, ev, data):
        if ev == MG_EV_HTTP_MSG:
            conn.reply(200, b"Goodbye!")

            # Graceful close - flushes send buffer first
            conn.drain()

            # Immediate close (may lose data)
            # conn.close()  # DON'T use this

Error Handling
--------------

.. automethod:: Connection.error

Example:

.. code-block:: python

    from cymongoose import MG_EV_ERROR

    def handler(conn, ev, data):
        if ev == MG_EV_ERROR:
            # data is error message string
            print(f"Error on connection {conn.id}: {data}")
            conn.close()

        # Trigger error manually
        if some_error_condition:
            conn.error("Custom error message")

See Also
--------

- :class:`Manager` - Event loop management
- :class:`HttpMessage`, :class:`WsMessage`, :class:`MqttMessage` - Message views
- :doc:`../guide/index` - Protocol guides
