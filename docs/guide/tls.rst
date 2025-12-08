TLS/SSL Guide
=============

This guide covers TLS/SSL encryption for secure connections.

TLS Configuration
-----------------

TlsOpts Class
~~~~~~~~~~~~~

.. code-block:: python

    from cymongoose import TlsOpts

    # Server with certificate and key
    server_opts = TlsOpts(
        cert=open("server.crt", "rb").read(),
        key=open("server.key", "rb").read()
    )

    # Client with custom CA
    client_opts = TlsOpts(
        ca=open("ca.crt", "rb").read(),
        name="example.com"  # SNI
    )

    # Development mode (skip verification - INSECURE!)
    dev_opts = TlsOpts(skip_verification=True)

HTTPS Server
------------

Basic HTTPS Server
~~~~~~~~~~~~~~~~~~

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

    # Generate private key and certificate
    openssl req -x509 -newkey rsa:2048 -keyout server.key \\
        -out server.crt -days 365 -nodes \\
        -subj "/CN=localhost"

HTTPS Client
------------

Client with Custom CA
~~~~~~~~~~~~~~~~~~~~~

.. code-block:: python

    from cymongoose import Manager, MG_EV_CONNECT, MG_EV_HTTP_MSG, TlsOpts

    ca = open("custom-ca.crt", "rb").read()

    def handler(conn, ev, data):
        if ev == MG_EV_CONNECT:
            # Initialize TLS
            opts = TlsOpts(ca=ca, name="example.com")
            conn.tls_init(opts)

            # Send request
            conn.send(b"GET / HTTP/1.1\\r\\nHost: example.com\\r\\n\\r\\n")

        elif ev == MG_EV_HTTP_MSG:
            print(data.body_text)
            conn.close()

    manager = Manager(handler)
    manager.connect('https://example.com:443', http=True)

Client with System CA
~~~~~~~~~~~~~~~~~~~~~

.. code-block:: python

    # Use system CA bundle
    ca = open("/etc/ssl/certs/ca-certificates.crt", "rb").read()
    opts = TlsOpts(ca=ca, name="example.com")

WebSocket Secure (WSS)
----------------------

WSS Server
~~~~~~~~~~

.. code-block:: python

    from cymongoose import MG_EV_ACCEPT, MG_EV_HTTP_MSG, MG_EV_WS_MSG

    cert = open("server.crt", "rb").read()
    key = open("server.key", "rb").read()

    def handler(conn, ev, data):
        if ev == MG_EV_ACCEPT:
            opts = TlsOpts(cert=cert, key=key)
            conn.tls_init(opts)

        elif ev == MG_EV_HTTP_MSG and data.uri == "/ws":
            conn.ws_upgrade(data)

        elif ev == MG_EV_WS_MSG:
            conn.ws_send(f"Echo: {data.text}")

    manager = Manager(handler)
    manager.listen('https://0.0.0.0:8443', http=True)

MQTTS (Secure MQTT)
-------------------

MQTTS Client
~~~~~~~~~~~~

.. code-block:: python

    from cymongoose import Manager, MG_EV_CONNECT, MG_EV_MQTT_OPEN, TlsOpts

    ca = open("ca.crt", "rb").read()

    def handler(conn, ev, data):
        if ev == MG_EV_CONNECT:
            opts = TlsOpts(ca=ca, name="broker.example.com")
            conn.tls_init(opts)

        elif ev == MG_EV_MQTT_OPEN:
            print("Secure MQTT connection established")
            conn.mqtt_sub("sensors/#", qos=1)

    manager = Manager(handler)
    manager.mqtt_connect('mqtts://broker.example.com:8883')

Certificate Verification
------------------------

Skip Verification (Development Only)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

**WARNING**: Only use for development/testing. Never in production!

.. code-block:: python

    # Skip certificate verification (INSECURE!)
    opts = TlsOpts(skip_verification=True)
    conn.tls_init(opts)

Custom CA Bundle
~~~~~~~~~~~~~~~~

.. code-block:: python

    # Load custom CA bundle
    ca = open("my-ca-bundle.crt", "rb").read()
    opts = TlsOpts(ca=ca)
    conn.tls_init(opts)

Client Certificate Authentication
----------------------------------

Mutual TLS (mTLS)
~~~~~~~~~~~~~~~~~

.. code-block:: python

    # Client provides certificate to server
    client_cert = open("client.crt", "rb").read()
    client_key = open("client.key", "rb").read()
    ca = open("ca.crt", "rb").read()

    opts = TlsOpts(
        ca=ca,
        cert=client_cert,
        key=client_key,
        name="server.example.com"
    )

    def handler(conn, ev, data):
        if ev == MG_EV_CONNECT:
            conn.tls_init(opts)

Production TLS Setup
--------------------

Let's Encrypt Certificates
~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: python

    # Use Let's Encrypt certificates
    cert = open("/etc/letsencrypt/live/example.com/fullchain.pem", "rb").read()
    key = open("/etc/letsencrypt/live/example.com/privkey.pem", "rb").read()

    opts = TlsOpts(cert=cert, key=key)

Best Practices
--------------

1. **Never skip verification** in production
2. **Use strong certificates** (2048-bit RSA minimum)
3. **Keep private keys secure** (file permissions 600)
4. **Rotate certificates** before expiry
5. **Use SNI** for virtual hosting
6. **Monitor certificate expiry** dates
7. **Test with real certificates** before deployment

Troubleshooting
---------------

Certificate Verification Failed
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

- Check CA bundle includes root certificate
- Verify certificate chain is complete
- Check certificate expiry date
- Ensure SNI name matches certificate

Connection Refused
~~~~~~~~~~~~~~~~~~

- Verify TLS port (443 for HTTPS, 8883 for MQTTS)
- Check firewall rules
- Ensure certificates are loaded correctly

See Also
--------

- :doc:`http` - HTTPS server/client
- :doc:`websocket` - Secure WebSocket
- :doc:`mqtt` - Secure MQTT
- :doc:`../advanced/troubleshooting` - Debugging TLS issues
