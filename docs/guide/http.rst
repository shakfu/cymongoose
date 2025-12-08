HTTP/HTTPS Guide
================

This guide covers HTTP and HTTPS servers and clients using cymongoose.

HTTP Server
-----------

Basic Server
~~~~~~~~~~~~

.. code-block:: python

    from cymongoose import Manager, MG_EV_HTTP_MSG

    def handler(conn, ev, data):
        if ev == MG_EV_HTTP_MSG:
            # Access request
            print(f"{data.method} {data.uri}")

            # Send response
            conn.reply(200, b'{"status": "ok"}',
                      headers={"Content-Type": "application/json"})
            conn.drain()

    manager = Manager(handler)
    manager.listen('http://0.0.0.0:8000', http=True)

    while True:
        manager.poll(100)

**Important**: Use ``http=True`` flag when calling ``listen()`` for HTTP servers.

Request Data
~~~~~~~~~~~~

Access request details from the :class:`~cymongoose.HttpMessage`:

.. code-block:: python

    def handler(conn, ev, data):
        if ev == MG_EV_HTTP_MSG:
            # Method: GET, POST, PUT, DELETE, etc.
            method = data.method

            # URI path
            uri = data.uri  # "/api/users/123"

            # Query string
            query = data.query  # "id=123&name=foo"
            user_id = data.query_var("id")  # "123"

            # Headers
            content_type = data.header("Content-Type")
            auth = data.header("Authorization")

            # All headers
            for name, value in data.headers():
                print(f"{name}: {value}")

            # Body
            body_bytes = data.body_bytes  # Raw bytes
            body_text = data.body_text    # UTF-8 decoded

Routing
~~~~~~~

Simple URL routing:

.. code-block:: python

    def handler(conn, ev, data):
        if ev == MG_EV_HTTP_MSG:
            method = data.method
            uri = data.uri

            # Route handlers
            if method == "GET" and uri == "/":
                conn.reply(200, b"Home page")

            elif method == "GET" and uri.startswith("/api/users/"):
                user_id = uri.split("/")[-1]
                handle_get_user(conn, user_id)

            elif method == "POST" and uri == "/api/users":
                handle_create_user(conn, data.body_text)

            else:
                conn.reply(404, b'{"error": "Not found"}',
                          headers={"Content-Type": "application/json"})

            conn.drain()

Static Files
~~~~~~~~~~~~

Serve files from a directory:

.. code-block:: python

    def handler(conn, ev, data):
        if ev == MG_EV_HTTP_MSG:
            if data.uri.startswith("/static/"):
                # Serve from ./public directory
                conn.serve_dir(data, "./public",
                              extra_headers="Cache-Control: max-age=3600")
            else:
                # Dynamic response
                conn.reply(200, b"Hello!")
                conn.drain()

Serve a single file:

.. code-block:: python

    if data.uri == "/favicon.ico":
        conn.serve_file(data, "./public/favicon.ico")

HTTP Responses
--------------

Simple Response
~~~~~~~~~~~~~~~

.. code-block:: python

    conn.reply(200, b"OK")

With Headers
~~~~~~~~~~~~

.. code-block:: python

    conn.reply(200, b'{"status": "ok"}',
              headers={
                  "Content-Type": "application/json",
                  "X-Request-ID": "12345",
              })

JSON Response
~~~~~~~~~~~~~

.. code-block:: python

    import json

    response_data = {"users": users, "count": len(users)}
    conn.reply(200, json.dumps(response_data).encode(),
              headers={"Content-Type": "application/json"})

HTML Response
~~~~~~~~~~~~~

.. code-block:: python

    html = b"""
    <html>
    <head><title>Hello</title></head>
    <body><h1>Hello, World!</h1></body>
    </html>
    """
    conn.reply(200, html,
              headers={"Content-Type": "text/html"})

HTTP Status Codes
~~~~~~~~~~~~~~~~~

.. code-block:: python

    # Success
    conn.reply(200, b"OK")
    conn.reply(201, b'{"id": 123}')  # Created
    conn.reply(204, b"")  # No Content

    # Client errors
    conn.reply(400, b"Bad Request")
    conn.reply(401, b"Unauthorized")
    conn.reply(403, b"Forbidden")
    conn.reply(404, b"Not Found")

    # Server errors
    conn.reply(500, b"Internal Server Error")
    conn.reply(503, b"Service Unavailable")

Streaming Responses
-------------------

Chunked Transfer Encoding
~~~~~~~~~~~~~~~~~~~~~~~~~~

For large or dynamically-generated responses:

.. code-block:: python

    def handler(conn, ev, data):
        if ev == MG_EV_HTTP_MSG:
            # Start chunked response
            conn.reply(200, "",
                      headers={"Transfer-Encoding": "chunked"})

            # Send chunks
            for i in range(100):
                chunk = f"Chunk {i}\\n"
                conn.http_chunk(chunk)

            # End chunking
            conn.http_chunk("")  # Empty chunk signals end

Server-Sent Events (SSE)
~~~~~~~~~~~~~~~~~~~~~~~~

Real-time server push:

.. code-block:: python

    # Track SSE connections
    sse_clients = []

    def handler(conn, ev, data):
        if ev == MG_EV_HTTP_MSG and data.uri == "/events":
            # Start SSE stream
            conn.reply(200, "",
                      headers={
                          "Content-Type": "text/event-stream",
                          "Cache-Control": "no-cache",
                      })
            sse_clients.append(conn)

    def broadcast_event(event_type, event_data):
        """Send event to all connected clients."""
        for client in sse_clients[:]:
            try:
                client.http_sse(event_type, event_data)
            except RuntimeError:
                sse_clients.remove(client)

    # Use with timer
    manager.timer_add(1000, lambda: broadcast_event("update", "..."),
                     repeat=True)

File Upload
-----------

Handle multipart form uploads:

.. code-block:: python

    from cymongoose import http_parse_multipart
    import os

    def handler(conn, ev, data):
        if ev == MG_EV_HTTP_MSG and data.method == "POST":
            os.makedirs("uploads", exist_ok=True)

            offset = 0
            while True:
                offset, part = http_parse_multipart(data.body_bytes, offset)
                if part is None:
                    break

                if part['filename']:
                    # File upload
                    filename = part['filename']
                    filepath = os.path.join("uploads", filename)

                    with open(filepath, "wb") as f:
                        f.write(part['body'])

                    print(f"Uploaded: {filepath}")

            conn.reply(200, b'{"status": "uploaded"}')
            conn.drain()

HTTP Client
-----------

Make HTTP Requests
~~~~~~~~~~~~~~~~~~

.. code-block:: python

    from cymongoose import Manager, MG_EV_CONNECT, MG_EV_HTTP_MSG

    def client_handler(conn, ev, data):
        if ev == MG_EV_CONNECT:
            # Send GET request
            conn.send(
                b"GET /api/data HTTP/1.1\\r\\n"
                b"Host: api.example.com\\r\\n"
                b"\\r\\n"
            )

        elif ev == MG_EV_HTTP_MSG:
            # Response received
            status = data.status()
            body = data.body_text

            print(f"Status: {status}")
            print(f"Body: {body}")

            conn.close()

    manager = Manager(client_handler)
    manager.connect('http://api.example.com:80', http=True)

POST Request
~~~~~~~~~~~~

.. code-block:: python

    def client_handler(conn, ev, data):
        if ev == MG_EV_CONNECT:
            import json
            payload = json.dumps({"name": "Alice"}).encode()

            request = (
                b"POST /api/users HTTP/1.1\\r\\n"
                b"Host: api.example.com\\r\\n"
                b"Content-Type: application/json\\r\\n"
                f"Content-Length: {len(payload)}\\r\\n".encode() +
                b"\\r\\n" +
                payload
            )
            conn.send(request)

HTTPS Server
------------

Setup TLS
~~~~~~~~~

.. code-block:: python

    from cymongoose import Manager, MG_EV_ACCEPT, MG_EV_HTTP_MSG, TlsOpts

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

Generate Self-Signed Certificate
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

For development/testing:

.. code-block:: bash

    openssl req -x509 -newkey rsa:2048 -keyout server.key \\
        -out server.crt -days 365 -nodes \\
        -subj "/CN=localhost"

See :doc:`tls` for production TLS configuration.

HTTPS Client
------------

.. code-block:: python

    from cymongoose import TlsOpts

    # Client with custom CA
    ca = open("custom-ca.crt", "rb").read()

    def client_handler(conn, ev, data):
        if ev == MG_EV_CONNECT:
            # Initialize TLS
            opts = TlsOpts(ca=ca, name="example.com")
            conn.tls_init(opts)

            # Send request after TLS handshake
            conn.send(b"GET / HTTP/1.1\\r\\nHost: example.com\\r\\n\\r\\n")

        elif ev == MG_EV_HTTP_MSG:
            print(f"Response: {data.body_text}")
            conn.close()

    manager = Manager(client_handler)
    manager.connect('https://example.com:443', http=True)

Best Practices
--------------

1. **Always use ``http=True``** flag for HTTP protocols
2. **Use ``conn.drain()``** for graceful connection close
3. **Set proper Content-Type** headers
4. **Handle errors** with appropriate status codes
5. **Use chunked encoding** for large responses
6. **Validate input** from query params and body

See Also
--------

- :doc:`websocket` - WebSocket upgrade from HTTP
- :doc:`tls` - TLS/SSL configuration
- :doc:`../api/connection` - Connection API reference
- :doc:`../examples` - Complete examples
