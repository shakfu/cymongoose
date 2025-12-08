Message View Classes
====================

.. currentmodule:: cymongoose

Message view classes provide zero-copy access to protocol-specific data structures.

HttpMessage
-----------

.. autoclass:: HttpMessage
   :members:
   :undoc-members:
   :member-order: bysource

Overview
~~~~~~~~

:class:`HttpMessage` provides access to HTTP request/response data without copying. It's a view over the underlying C ``mg_http_message`` struct.

**Lifetime**: Only valid within the event handler for ``MG_EV_HTTP_MSG`` or ``MG_EV_HTTP_HDRS`` events.

Example
~~~~~~~

.. code-block:: python

    from cymongoose import MG_EV_HTTP_MSG

    def handler(conn, ev, data):
        if ev == MG_EV_HTTP_MSG:
            # data is HttpMessage
            print(f"{data.method} {data.uri}")

            # Query parameters
            user_id = data.query_var("id")

            # Headers
            content_type = data.header("Content-Type")
            for name, value in data.headers():
                print(f"{name}: {value}")

            # Body
            body = data.body_bytes  # bytes
            text = data.body_text   # str

            # Status (for responses)
            if data.status():
                print(f"HTTP {data.status()}")

WsMessage
---------

.. autoclass:: WsMessage
   :members:
   :undoc-members:
   :member-order: bysource

Overview
~~~~~~~~

:class:`WsMessage` provides access to WebSocket frame data.

**Lifetime**: Only valid within ``MG_EV_WS_MSG`` event handler.

Example
~~~~~~~

.. code-block:: python

    from cymongoose import (
        MG_EV_WS_MSG,
        WEBSOCKET_OP_TEXT,
        WEBSOCKET_OP_BINARY,
        WEBSOCKET_OP_PING,
        WEBSOCKET_OP_PONG,
    )

    def handler(conn, ev, data):
        if ev == MG_EV_WS_MSG:
            # data is WsMessage
            if data.flags == WEBSOCKET_OP_TEXT:
                print(f"Text: {data.text}")
            elif data.flags == WEBSOCKET_OP_BINARY:
                print(f"Binary: {len(data.data)} bytes")
            elif data.flags == WEBSOCKET_OP_PING:
                # Respond to ping
                conn.ws_send(b"", WEBSOCKET_OP_PONG)

MqttMessage
-----------

.. autoclass:: MqttMessage
   :members:
   :undoc-members:
   :member-order: bysource

Overview
~~~~~~~~

:class:`MqttMessage` provides access to MQTT message data.

**Lifetime**: Only valid within ``MG_EV_MQTT_MSG`` or ``MG_EV_MQTT_CMD`` event handlers.

Example
~~~~~~~

.. code-block:: python

    from cymongoose import MG_EV_MQTT_MSG, MG_EV_MQTT_CMD

    def handler(conn, ev, data):
        if ev == MG_EV_MQTT_MSG:
            # data is MqttMessage
            print(f"Topic: {data.topic}")
            print(f"Message: {data.text}")
            print(f"QoS: {data.qos}")
            print(f"Message ID: {data.id}")

            # Parse JSON payload
            import json
            payload = json.loads(data.text)

        elif ev == MG_EV_MQTT_CMD:
            # MQTT command (CONNECT, SUBSCRIBE, etc.)
            print(f"Command: {data.cmd}")

TlsOpts
-------

.. autoclass:: TlsOpts
   :members:
   :undoc-members:
   :special-members: __init__
   :member-order: bysource

Overview
~~~~~~~~

:class:`TlsOpts` configures TLS/SSL settings for secure connections.

Example
~~~~~~~

.. code-block:: python

    from cymongoose import TlsOpts, MG_EV_ACCEPT

    # Server with certificate
    cert = open("server.crt", "rb").read()
    key = open("server.key", "rb").read()

    server_opts = TlsOpts(cert=cert, key=key)

    # Client with custom CA
    ca = open("custom-ca.crt", "rb").read()
    client_opts = TlsOpts(ca=ca, name="example.com")

    # Development mode (skip verification - INSECURE!)
    dev_opts = TlsOpts(skip_verification=True)

    def handler(conn, ev, data):
        if ev == MG_EV_ACCEPT:
            # Initialize TLS on new connection
            conn.tls_init(server_opts)

Timer
-----

.. autoclass:: Timer
   :members:
   :undoc-members:
   :member-order: bysource

Overview
~~~~~~~~

:class:`Timer` wraps Mongoose timers. Timers are automatically freed when they complete (``MG_TIMER_AUTODELETE`` flag).

**Note**: Do not create Timer objects directly. Use :meth:`Manager.timer_add`.

Example
~~~~~~~

.. code-block:: python

    # One-shot timer
    timer = manager.timer_add(5000, lambda: print("Hello"))

    # Repeating timer
    counter = 0
    def heartbeat():
        global counter
        counter += 1
        print(f"Heartbeat #{counter}")

    timer = manager.timer_add(1000, heartbeat, repeat=True)

    # Run immediately and repeat
    timer = manager.timer_add(1000, callback, repeat=True, run_now=True)

Event Data Types
----------------

Different events provide different data types:

.. list-table::
   :header-rows: 1
   :widths: 30 30 40

   * - Event
     - Data Type
     - Description
   * - ``MG_EV_ERROR``
     - ``str``
     - Error message
   * - ``MG_EV_RESOLVE``
     - ``None``
     - DNS resolved (check ``conn.remote_addr``)
   * - ``MG_EV_HTTP_MSG``
     - :class:`HttpMessage`
     - Complete HTTP message
   * - ``MG_EV_HTTP_HDRS``
     - :class:`HttpMessage`
     - HTTP headers only
   * - ``MG_EV_WS_OPEN``
     - :class:`HttpMessage`
     - WebSocket handshake request
   * - ``MG_EV_WS_MSG``
     - :class:`WsMessage`
     - WebSocket frame
   * - ``MG_EV_MQTT_MSG``
     - :class:`MqttMessage`
     - MQTT message
   * - ``MG_EV_MQTT_CMD``
     - :class:`MqttMessage`
     - MQTT command
   * - ``MG_EV_MQTT_OPEN``
     - ``int``
     - Connection status code
   * - ``MG_EV_SNTP_TIME``
     - ``int``
     - Milliseconds since epoch
   * - ``MG_EV_WAKEUP``
     - ``bytes``
     - Wakeup payload data
   * - Others
     - ``None``
     - No data

See Also
--------

- :class:`Connection` - Connection class
- :class:`Manager` - Manager class
- :doc:`../guide/index` - Protocol guides
