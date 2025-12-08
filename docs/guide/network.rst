Network Protocols Guide
=======================

This guide covers TCP, UDP, DNS, and SNTP protocols.

TCP
---

TCP Server
~~~~~~~~~~

.. code-block:: python

    from cymongoose import Manager, MG_EV_ACCEPT, MG_EV_READ

    def handler(conn, ev, data):
        if ev == MG_EV_ACCEPT:
            print(f"Client connected: {conn.remote_addr}")

        elif ev == MG_EV_READ:
            # Read data
            data = conn.recv_data()
            print(f"Received: {data}")

            # Echo back
            conn.send(data)

    manager = Manager(handler)
    manager.listen('tcp://0.0.0.0:1234')

    while True:
        manager.poll(100)

TCP Client
~~~~~~~~~~

.. code-block:: python

    from cymongoose import Manager, MG_EV_CONNECT, MG_EV_READ

    def handler(conn, ev, data):
        if ev == MG_EV_CONNECT:
            # Connected to server
            print("Connected")
            conn.send(b"Hello, Server!")

        elif ev == MG_EV_READ:
            # Response received
            data = conn.recv_data()
            print(f"Received: {data}")
            conn.close()

    manager = Manager(handler)
    manager.connect('tcp://localhost:1234')

    while True:
        manager.poll(100)

UDP
---

UDP Server
~~~~~~~~~~

.. code-block:: python

    from cymongoose import Manager, MG_EV_READ

    def handler(conn, ev, data):
        if ev == MG_EV_READ:
            # Receive datagram
            data = conn.recv_data()
            print(f"Received from {conn.remote_addr}: {data}")

            # Echo back
            conn.send(data)

    manager = Manager(handler)
    manager.listen('udp://0.0.0.0:5678')

    while True:
        manager.poll(100)

UDP Client
~~~~~~~~~~

.. code-block:: python

    from cymongoose import Manager, MG_EV_CONNECT, MG_EV_READ

    def handler(conn, ev, data):
        if ev == MG_EV_CONNECT:
            # Send datagram
            conn.send(b"Hello, UDP!")

        elif ev == MG_EV_READ:
            # Response received
            data = conn.recv_data()
            print(f"Received: {data}")

    manager = Manager(handler)
    manager.connect('udp://localhost:5678')

    while True:
        manager.poll(100)

DNS Resolution
--------------

Async DNS Lookup
~~~~~~~~~~~~~~~~

.. code-block:: python

    from cymongoose import Manager, MG_EV_OPEN, MG_EV_RESOLVE

    def handler(conn, ev, data):
        if ev == MG_EV_OPEN:
            # Start DNS resolution
            conn.resolve("example.com")

        elif ev == MG_EV_RESOLVE:
            # Resolution complete
            ip, port, is_ipv6 = conn.remote_addr
            print(f"Resolved to: {ip}")
            conn.close()

    manager = Manager(handler)
    conn = manager.connect('tcp://0.0.0.0:0')  # Dummy connection for resolution

    while True:
        manager.poll(100)

Cancel DNS Lookup
~~~~~~~~~~~~~~~~~

.. code-block:: python

    def handler(conn, ev, data):
        if ev == MG_EV_OPEN:
            conn.resolve("example.com")

            # Cancel after 1 second
            def cancel():
                conn.resolve_cancel()

            manager.timer_add(1000, cancel)

SNTP (Time Sync)
----------------

Get Network Time
~~~~~~~~~~~~~~~~

.. code-block:: python

    from cymongoose import Manager, MG_EV_SNTP_TIME
    import datetime

    def handler(conn, ev, data):
        if ev == MG_EV_CONNECT:
            # Request time
            conn.sntp_request()

        elif ev == MG_EV_SNTP_TIME:
            # Time received (milliseconds since epoch)
            dt = datetime.datetime.fromtimestamp(data / 1000.0)
            print(f"Server time: {dt}")
            conn.close()

    manager = Manager(handler)
    manager.sntp_connect('udp://time.google.com:123')

    while True:
        manager.poll(100)

Periodic Time Sync
~~~~~~~~~~~~~~~~~~

.. code-block:: python

    def handler(conn, ev, data):
        if ev == MG_EV_SNTP_TIME:
            dt = datetime.datetime.fromtimestamp(data / 1000.0)
            print(f"Synced time: {dt}")

    manager = Manager(handler)
    conn = manager.sntp_connect('udp://time.google.com:123')

    # Sync every 10 seconds
    def sync_time():
        conn.sntp_request()

    manager.timer_add(10000, sync_time, repeat=True, run_now=True)

See Also
--------

- :doc:`tls` - Secure TCP with TLS
- :doc:`../api/connection` - Connection API
- :doc:`../examples` - Complete examples
