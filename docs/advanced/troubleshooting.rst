Troubleshooting Guide
=====================

Common issues and solutions for cymongoose applications.

Build Issues
------------

"Cython not found"
~~~~~~~~~~~~~~~~~~

**Error**:

.. code-block:: text

    ModuleNotFoundError: No module named 'Cython'

**Solution**:

.. code-block:: bash

    pip install cython
    pip install -e .

"C compiler not found"
~~~~~~~~~~~~~~~~~~~~~~

**Error**:

.. code-block:: text

    error: Microsoft Visual C++ 14.0 or greater is required

**Solutions**:

- **Linux**: ``sudo apt-get install build-essential``
- **macOS**: ``xcode-select --install``
- **Windows**: Install Visual Studio with C++ tools

"mongoose.h not found"
~~~~~~~~~~~~~~~~~~~~~~

**Error**:

.. code-block:: text

    fatal error: mongoose.h: No such file or directory

**Solution**:

Mongoose is vendored in ``thirdparty/mongoose/``. Ensure complete clone:

.. code-block:: bash

    git clone --recursive https://github.com/your-username/cymongoose.git

Import Errors
-------------

"cannot import name 'Manager'"
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

**Cause**: Extension not built

**Solution**:

.. code-block:: bash

    pip install -e . --force-reinstall

"Symbol not found" on macOS
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

**Error**:

.. code-block:: text

    Symbol not found: _mg_listen

**Solution**: Rebuild without cache:

.. code-block:: bash

    pip uninstall cymongoose
    pip install -e . --no-cache-dir

Runtime Issues
--------------

Ctrl+C Not Working
~~~~~~~~~~~~~~~~~~

**Symptom**: Pressing Ctrl+C doesn't stop the server

**Cause**: With nogil, ``KeyboardInterrupt`` may be delayed

**Solution**: Use signal handlers:

.. code-block:: python

    import signal

    shutdown_requested = False

    def signal_handler(sig, frame):
        global shutdown_requested
        shutdown_requested = True

    signal.signal(signal.SIGINT, signal_handler)

    while not shutdown_requested:
        manager.poll(100)

See :doc:`shutdown` for details.

HTTP Server Not Responding
~~~~~~~~~~~~~~~~~~~~~~~~~~~

**Symptom**: Requests timeout or no response

**Causes & Solutions**:

1. **Missing ``http=True`` flag**:

   .. code-block:: python

       # Bad
       manager.listen('http://0.0.0.0:8000')  # Won't parse HTTP!

       # Good
       manager.listen('http://0.0.0.0:8000', http=True)

2. **Handler not calling ``reply()``**:

   .. code-block:: python

       def handler(conn, ev, data):
           if ev == MG_EV_HTTP_MSG:
               # Must send response
               conn.reply(200, b"OK")
               conn.drain()

3. **Firewall blocking port**:

   .. code-block:: bash

       # Check if port is accessible
       curl http://localhost:8000

Connections Not Closing
~~~~~~~~~~~~~~~~~~~~~~~~

**Symptom**: Connections remain open after sending response

**Cause**: Using ``conn.close()`` instead of ``conn.drain()``

**Solution**:

.. code-block:: python

    # Bad
    conn.reply(200, b"OK")
    conn.close()  # May lose data

    # Good
    conn.reply(200, b"OK")
    conn.drain()  # Graceful close

Performance Issues
------------------

Low Throughput
~~~~~~~~~~~~~~

**Symptom**: Lower req/sec than expected (< 30k req/sec)

**Checks**:

1. **Verify nogil is enabled**:

   .. code-block:: text

       # Should see at startup:
       USE_NOGIL=1

   If not, rebuild:

   .. code-block:: bash

       rm src/cymongoose/_mongoose.c
       pip install -e . --force-reinstall

2. **Check poll timeout**:

   .. code-block:: python

       # Bad: Long timeout doesn't affect throughput
       # but affects shutdown time
       manager.poll(5000)

       # Good
       manager.poll(100)

3. **Profile handler**:

   .. code-block:: python

       import time

       def handler(conn, ev, data):
           start = time.perf_counter()
           # ... handle event
           elapsed = time.perf_counter() - start
           if elapsed > 0.001:  # > 1ms
               print(f"Slow: {elapsed*1000:.2f}ms")

High CPU Usage
~~~~~~~~~~~~~~

**Symptom**: 100% CPU when idle

**Cause**: Zero poll timeout (busy loop)

**Solution**:

.. code-block:: python

    # Bad: Busy loop
    manager.poll(0)

    # Good: 100ms timeout
    manager.poll(100)

Memory Leaks
~~~~~~~~~~~~

**Symptom**: Memory usage grows over time

**Causes**:

1. **Not removing closed connections from lists**:

   .. code-block:: python

       def handler(conn, ev, data):
           if ev == MG_EV_ACCEPT:
               clients.append(conn)

           elif ev == MG_EV_CLOSE:
               # IMPORTANT: Clean up
               if conn in clients:
                   clients.remove(conn)

2. **Holding Connection references**:

   .. code-block:: python

       # Bad: Global reference prevents cleanup
       last_conn = None

       def handler(conn, ev, data):
           global last_conn
           last_conn = conn  # Keeps connection alive!

WebSocket Issues
----------------

"Upgrade failed"
~~~~~~~~~~~~~~~~

**Cause**: Not using ``http=True`` flag

**Solution**:

.. code-block:: python

    manager.listen('http://0.0.0.0:8000', http=True)  # Required!

"Connection closed immediately"
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

**Cause**: Calling ``conn.drain()`` or ``conn.close()`` after ``ws_upgrade()``

**Solution**:

.. code-block:: python

    def handler(conn, ev, data):
        if ev == MG_EV_HTTP_MSG and data.uri == "/ws":
            conn.ws_upgrade(data)
            # DON'T call drain() or close() here!

        elif ev == MG_EV_WS_MSG:
            # Now you can send/receive
            conn.ws_send("Hello!")

MQTT Issues
-----------

"Connection refused"
~~~~~~~~~~~~~~~~~~~~

**Causes**:

1. Broker not running
2. Wrong port (1883 for MQTT, 8883 for MQTTS)
3. Firewall blocking connection

**Solution**: Test with mosquitto_sub:

.. code-block:: bash

    # Test broker connectivity
    mosquitto_sub -h broker.hivemq.com -t test/# -v

"Not receiving messages"
~~~~~~~~~~~~~~~~~~~~~~~~

**Cause**: Not subscribing after connection

**Solution**:

.. code-block:: python

    def handler(conn, ev, data):
        if ev == MG_EV_MQTT_OPEN:
            # Subscribe AFTER connection
            conn.mqtt_sub("sensors/#", qos=1)

TLS Issues
----------

"Certificate verification failed"
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

**Causes**:

1. CA bundle doesn't include root certificate
2. Certificate expired
3. Hostname mismatch

**Solutions**:

.. code-block:: python

    # 1. Check expiry
    # openssl x509 -in cert.pem -noout -enddate

    # 2. Verify hostname
    opts = TlsOpts(ca=ca, name="exact.hostname.com")

    # 3. For development only (INSECURE!)
    opts = TlsOpts(skip_verification=True)

"handshake failure"
~~~~~~~~~~~~~~~~~~~

**Cause**: Missing certificate or key

**Solution**:

.. code-block:: python

    # Server needs both cert and key
    cert = open("server.crt", "rb").read()
    key = open("server.key", "rb").read()

    opts = TlsOpts(cert=cert, key=key)
    conn.tls_init(opts)

Multi-Threading Issues
----------------------

"RuntimeError: Connection has been closed"
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

**Cause**: Passing Connection object to thread

**Solution**: Pass connection ID:

.. code-block:: python

    # Bad
    work_queue.put({'conn': conn})  # UNSAFE!

    # Good
    work_queue.put({'conn_id': conn.id})  # Safe

"Wakeup not working"
~~~~~~~~~~~~~~~~~~~~

**Cause**: Forgot to enable wakeup support

**Solution**:

.. code-block:: python

    # Enable wakeup when creating manager
    manager = Manager(handler, enable_wakeup=True)

Getting Help
------------

1. **Check logs**: Enable verbose logging
2. **Search issues**: https://github.com/your-username/cymongoose/issues
3. **Minimal reproduction**: Create smallest example that shows the issue
4. **System info**: Python version, OS, cymongoose version

Reporting Issues:

.. code-block:: bash

    # Include this info
    python --version
    uv run python -c "import cymongoose; print(cymongoose.__version__)"
    uname -a

See Also
--------

- :doc:`shutdown` - Graceful shutdown patterns
- :doc:`nogil` - nogil optimization
- :doc:`performance` - Performance tuning
