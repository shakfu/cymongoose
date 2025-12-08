API Reference
=============

Complete API documentation for all cymongoose classes, functions, and constants.

Core Classes
------------

.. toctree::
   :maxdepth: 2

   manager
   connection
   messages
   utilities

Quick Reference
---------------

Manager
~~~~~~~

The :class:`~cymongoose.Manager` class manages the event loop and connections:

.. code-block:: python

    from cymongoose import Manager

    # Create manager
    manager = Manager(default_handler)

    # Listen for connections
    listener = manager.listen('http://0.0.0.0:8000', http=True)

    # Make outbound connections
    conn = manager.connect('http://example.com', http=True)

    # MQTT
    mqtt_conn = manager.mqtt_connect('mqtt://broker.com:1883')

    # Timers
    timer = manager.timer_add(1000, callback, repeat=True)

    # Event loop
    manager.poll(100)

    # Cleanup
    manager.close()

Connection
~~~~~~~~~~

The :class:`~cymongoose.Connection` class represents a network connection:

.. code-block:: python

    # Send data
    conn.send(b"Hello")
    conn.reply(200, b"OK")  # HTTP response

    # WebSocket
    conn.ws_upgrade(http_message)
    conn.ws_send("Hello WebSocket!")

    # MQTT
    conn.mqtt_pub("topic", "message", qos=1)
    conn.mqtt_sub("topic/#", qos=1)

    # Connection info
    local_ip, local_port, is_ipv6 = conn.local_addr
    remote_ip, remote_port, is_ipv6 = conn.remote_addr

    # Flow control
    if conn.is_full:
        print("Backpressure - stop sending")

    # Graceful close
    conn.drain()

Message Views
~~~~~~~~~~~~~

Event data is wrapped in message view objects:

.. code-block:: python

    # HttpMessage
    def handler(conn, ev, data):
        if ev == MG_EV_HTTP_MSG:
            print(data.method)  # GET, POST, etc.
            print(data.uri)     # /path
            print(data.query)   # query string
            param = data.query_var("id")
            header = data.header("Content-Type")
            body = data.body_bytes

    # WsMessage
    def handler(conn, ev, data):
        if ev == MG_EV_WS_MSG:
            print(data.text)    # UTF-8 text
            print(data.data)    # Raw bytes
            print(data.flags)   # Frame flags

    # MqttMessage
    def handler(conn, ev, data):
        if ev == MG_EV_MQTT_MSG:
            print(data.topic)   # Topic
            print(data.text)    # Message
            print(data.qos)     # QoS level

Event Constants
~~~~~~~~~~~~~~~

Event types for the event handler:

.. code-block:: python

    from cymongoose import (
        MG_EV_ERROR,      # Error occurred
        MG_EV_OPEN,       # Connection opened
        MG_EV_POLL,       # Poll event
        MG_EV_RESOLVE,    # DNS resolution complete
        MG_EV_CONNECT,    # Outbound connection established
        MG_EV_ACCEPT,     # Inbound connection accepted
        MG_EV_TLS_HS,     # TLS handshake complete
        MG_EV_READ,       # Data available to read
        MG_EV_WRITE,      # Ready to write
        MG_EV_CLOSE,      # Connection closing
        MG_EV_HTTP_HDRS,  # HTTP headers received
        MG_EV_HTTP_MSG,   # Complete HTTP message
        MG_EV_WS_OPEN,    # WebSocket handshake
        MG_EV_WS_MSG,     # WebSocket message
        MG_EV_WS_CTL,     # WebSocket control frame
        MG_EV_MQTT_CMD,   # MQTT command
        MG_EV_MQTT_MSG,   # MQTT message
        MG_EV_MQTT_OPEN,  # MQTT connection
        MG_EV_SNTP_TIME,  # SNTP time received
        MG_EV_WAKEUP,     # Wakeup notification
        MG_EV_USER,       # User-defined events
    )

Protocol Constants
~~~~~~~~~~~~~~~~~~

.. code-block:: python

    from cymongoose import (
        WEBSOCKET_OP_TEXT,
        WEBSOCKET_OP_BINARY,
        WEBSOCKET_OP_PING,
        WEBSOCKET_OP_PONG,
    )

Utility Functions
~~~~~~~~~~~~~~~~~

.. code-block:: python

    from cymongoose import (
        json_get,
        json_get_num,
        json_get_bool,
        json_get_long,
        json_get_str,
        url_encode,
        http_parse_multipart,
    )

    # JSON parsing
    value = json_get(json_str, "$.user.name")
    count = json_get_num(json_str, "$.count", default=0)

    # URL encoding
    encoded = url_encode("hello world")  # "hello%20world"

    # Multipart forms
    offset, part = http_parse_multipart(body, 0)

Full Documentation
------------------

See the detailed pages for complete API documentation with all methods, properties, and examples.
