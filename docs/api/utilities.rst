Utility Functions
=================

.. currentmodule:: cymongoose

cymongoose provides utility functions for JSON parsing, URL encoding, and multipart form handling.

JSON Utilities
--------------

Mongoose includes a lightweight JSON parser. These functions extract values from JSON without full parsing.

json_get
~~~~~~~~

.. autofunction:: json_get

Example:

.. code-block:: python

    json_str = '{"user": {"name": "Alice", "age": 30}, "items": [1, 2, 3]}'

    # Get nested value
    name = json_get(json_str, "$.user.name")  # "Alice"

    # Get array element
    first = json_get(json_str, "$.items[0]")  # "1"

json_get_num
~~~~~~~~~~~~

.. autofunction:: json_get_num

Example:

.. code-block:: python

    json_str = '{"temperature": 23.5, "humidity": 65}'

    temp = json_get_num(json_str, "$.temperature")  # 23.5
    pressure = json_get_num(json_str, "$.pressure", default=0.0)  # 0.0

json_get_bool
~~~~~~~~~~~~~

.. autofunction:: json_get_bool

Example:

.. code-block:: python

    json_str = '{"enabled": true, "debug": false}'

    enabled = json_get_bool(json_str, "$.enabled")  # True
    debug = json_get_bool(json_str, "$.debug")  # False
    missing = json_get_bool(json_str, "$.other", default=False)  # False

json_get_long
~~~~~~~~~~~~~

.. autofunction:: json_get_long

Example:

.. code-block:: python

    json_str = '{"count": 12345, "id": 9876543210}'

    count = json_get_long(json_str, "$.count")  # 12345
    user_id = json_get_long(json_str, "$.id")  # 9876543210
    missing = json_get_long(json_str, "$.other", default=0)  # 0

json_get_str
~~~~~~~~~~~~

.. autofunction:: json_get_str

Example:

.. code-block:: python

    json_str = '{"message": "Hello, World!", "path": "/home/user"}'

    # Automatically unescapes JSON strings
    message = json_get_str(json_str, "$.message")  # "Hello, World!"
    path = json_get_str(json_str, "$.path")  # "/home/user"

Complete JSON Parsing Example
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: python

    from cymongoose import (
        json_get,
        json_get_num,
        json_get_bool,
        json_get_long,
        json_get_str,
    )

    def handler(conn, ev, data):
        if ev == MG_EV_HTTP_MSG:
            json_body = data.body_text

            # Parse different types
            user_id = json_get_long(json_body, "$.user.id")
            username = json_get_str(json_body, "$.user.name")
            age = json_get_num(json_body, "$.user.age")
            active = json_get_bool(json_body, "$.user.active")

            # Build response
            response = {
                "id": user_id,
                "name": username,
                "age": age,
                "active": active,
            }

            import json
            conn.reply(200, json.dumps(response).encode())

URL Encoding
------------

url_encode
~~~~~~~~~~

.. autofunction:: url_encode

Example:

.. code-block:: python

    # Encode query parameters
    param = url_encode("hello world")  # "hello%20world"
    email = url_encode("user@example.com")  # "user%40example.com"

    # Build query string
    query = f"name={url_encode(name)}&email={url_encode(email)}"

    # Make request
    url = f"http://example.com/api?{query}"
    conn = manager.connect(url, http=True)

Multipart Form Data
-------------------

http_parse_multipart
~~~~~~~~~~~~~~~~~~~~

.. autofunction:: http_parse_multipart

Example:

.. code-block:: python

    from cymongoose import MG_EV_HTTP_MSG, http_parse_multipart

    def handler(conn, ev, data):
        if ev == MG_EV_HTTP_MSG and data.method == "POST":
            # Parse multipart form data
            offset = 0
            while True:
                offset, part = http_parse_multipart(data.body_bytes, offset)
                if part is None:
                    break  # No more parts

                # Field name
                field_name = part['name']

                # File upload
                if part['filename']:
                    filename = part['filename']
                    file_data = part['body']
                    print(f"File upload: {filename} ({len(file_data)} bytes)")

                    # Save file
                    with open(f"uploads/{filename}", "wb") as f:
                        f.write(file_data)
                else:
                    # Regular form field
                    field_value = part['body'].decode('utf-8')
                    print(f"Field: {field_name} = {field_value}")

            conn.reply(200, b'{"status": "uploaded"}')
            conn.drain()

File Upload Server Example
~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: python

    import os
    from cymongoose import Manager, MG_EV_HTTP_MSG, http_parse_multipart

    def handler(conn, ev, data):
        if ev == MG_EV_HTTP_MSG:
            if data.method == "POST" and data.uri == "/upload":
                os.makedirs("uploads", exist_ok=True)

                offset = 0
                uploaded_files = []

                while True:
                    offset, part = http_parse_multipart(data.body_bytes, offset)
                    if part is None:
                        break

                    if part['filename']:
                        # Save uploaded file
                        filename = part['filename']
                        filepath = os.path.join("uploads", filename)

                        with open(filepath, "wb") as f:
                            f.write(part['body'])

                        uploaded_files.append(filename)
                        print(f"Saved: {filepath}")

                # Return success response
                import json
                response = {
                    "status": "success",
                    "files": uploaded_files,
                }
                conn.reply(200, json.dumps(response).encode(),
                          headers={"Content-Type": "application/json"})
            else:
                # Serve upload form
                html = b"""
                <html>
                <body>
                    <h1>File Upload</h1>
                    <form method="POST" action="/upload"
                          enctype="multipart/form-data">
                        <input type="file" name="files" multiple>
                        <button type="submit">Upload</button>
                    </form>
                </body>
                </html>
                """
                conn.reply(200, html,
                          headers={"Content-Type": "text/html"})
            conn.drain()

Constants
---------

Event Types
~~~~~~~~~~~

See :doc:`../guide/index` for event handling details.

.. code-block:: python

    from cymongoose import (
        MG_EV_ERROR,
        MG_EV_OPEN,
        MG_EV_POLL,
        MG_EV_RESOLVE,
        MG_EV_CONNECT,
        MG_EV_ACCEPT,
        MG_EV_TLS_HS,
        MG_EV_READ,
        MG_EV_WRITE,
        MG_EV_CLOSE,
        MG_EV_HTTP_HDRS,
        MG_EV_HTTP_MSG,
        MG_EV_WS_OPEN,
        MG_EV_WS_MSG,
        MG_EV_WS_CTL,
        MG_EV_MQTT_CMD,
        MG_EV_MQTT_MSG,
        MG_EV_MQTT_OPEN,
        MG_EV_SNTP_TIME,
        MG_EV_WAKEUP,
        MG_EV_USER,
    )

WebSocket Opcodes
~~~~~~~~~~~~~~~~~

.. code-block:: python

    from cymongoose import (
        WEBSOCKET_OP_TEXT,
        WEBSOCKET_OP_BINARY,
        WEBSOCKET_OP_PING,
        WEBSOCKET_OP_PONG,
    )

    # Use with ws_send()
    conn.ws_send("Hello", WEBSOCKET_OP_TEXT)
    conn.ws_send(b"\\x00\\x01\\x02", WEBSOCKET_OP_BINARY)

See Also
--------

- :class:`HttpMessage` - HTTP message access
- :class:`Connection` - Connection methods
- :doc:`../examples` - Complete examples
