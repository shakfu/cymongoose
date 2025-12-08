User Guide
==========

This guide covers protocol-specific usage patterns and best practices for cymongoose.

.. toctree::
   :maxdepth: 2

   http
   websocket
   mqtt
   network
   tls

Overview
--------

cymongoose is organized around an event-driven architecture. Your application creates a :class:`~cymongoose.Manager`, registers event handlers, and runs the event loop.

Basic Pattern
-------------

All cymongoose applications follow this pattern:

.. code-block:: python

    import signal
    from cymongoose import Manager

    shutdown_requested = False

    def signal_handler(sig, frame):
        global shutdown_requested
        shutdown_requested = True

    def event_handler(conn, ev, data):
        # Handle events
        pass

    def main():
        global shutdown_requested

        # Setup signal handlers
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)

        # Create manager
        manager = Manager(event_handler)

        # Listen or connect
        manager.listen('http://0.0.0.0:8000', http=True)

        # Event loop
        try:
            while not shutdown_requested:
                manager.poll(100)  # 100ms timeout
            print("Shutting down...")
        finally:
            manager.close()

    if __name__ == "__main__":
        main()

Event Handler
-------------

The event handler receives three arguments:

.. code-block:: python

    def handler(conn, ev, data):
        """
        Args:
            conn: Connection object
            ev: Event type (integer constant)
            data: Event-specific data (or None)
        """
        if ev == MG_EV_HTTP_MSG:
            # data is HttpMessage
            print(f"{data.method} {data.uri}")

        elif ev == MG_EV_WS_MSG:
            # data is WsMessage
            print(f"WebSocket: {data.text}")

        elif ev == MG_EV_MQTT_MSG:
            # data is MqttMessage
            print(f"{data.topic}: {data.text}")

Common Events
~~~~~~~~~~~~~

.. list-table::
   :header-rows: 1

   * - Event
     - When Fired
     - Data Type
   * - ``MG_EV_ERROR``
     - Error occurred
     - ``str``
   * - ``MG_EV_OPEN``
     - Connection opened
     - ``None``
   * - ``MG_EV_ACCEPT``
     - Incoming connection
     - ``None``
   * - ``MG_EV_CONNECT``
     - Outbound connection established
     - ``None``
   * - ``MG_EV_CLOSE``
     - Connection closing
     - ``None``
   * - ``MG_EV_READ``
     - Data available
     - ``None``
   * - ``MG_EV_WRITE``
     - Ready to write
     - ``None``

Best Practices
--------------

Signal Handling
~~~~~~~~~~~~~~~

Use signal handlers instead of try/except for Ctrl+C:

.. code-block:: python

    shutdown_requested = False

    def signal_handler(sig, frame):
        global shutdown_requested
        shutdown_requested = True

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

**Why?** The event loop releases the GIL for performance, which delays ``KeyboardInterrupt`` handling.

Graceful Shutdown
~~~~~~~~~~~~~~~~~

Use ``conn.drain()`` instead of ``conn.close()``:

.. code-block:: python

    def handler(conn, ev, data):
        if ev == MG_EV_HTTP_MSG:
            conn.reply(200, b"Goodbye!")
            conn.drain()  # Flushes send buffer before closing

Poll Timeout
~~~~~~~~~~~~

Use ``poll(100)`` for responsive shutdown with low CPU:

.. code-block:: python

    while not shutdown_requested:
        manager.poll(100)  # 100ms - responsive and efficient

Error Handling
~~~~~~~~~~~~~~

Handle errors in the event callback:

.. code-block:: python

    def handler(conn, ev, data):
        if ev == MG_EV_ERROR:
            print(f"Error: {data}")
            conn.close()

        try:
            # Your event handling
            if ev == MG_EV_HTTP_MSG:
                process_request(conn, data)
        except Exception as e:
            print(f"Handler error: {e}")
            conn.reply(500, b"Internal Server Error")
            conn.drain()

Per-Protocol Guides
-------------------

See the protocol-specific guides for detailed information:

- :doc:`http` - HTTP/HTTPS servers and clients
- :doc:`websocket` - WebSocket communication
- :doc:`mqtt` - MQTT publish/subscribe
- :doc:`network` - TCP/UDP, DNS, SNTP
- :doc:`tls` - TLS/SSL configuration

Advanced Topics
---------------

For performance optimization, threading, and other advanced topics:

- :doc:`../advanced/nogil` - GIL-free performance optimization
- :doc:`../advanced/threading` - Multi-threaded patterns
- :doc:`../advanced/performance` - Performance tuning
- :doc:`../advanced/shutdown` - Proper shutdown handling

Next Steps
----------

- Follow :doc:`http` guide for web servers
- See :doc:`websocket` for real-time communication
- Check :doc:`../examples` for complete examples
