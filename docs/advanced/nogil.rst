GIL-Free Performance Optimization
==================================

cymongoose achieves C-level performance through the ``nogil`` optimization.

Overview
--------

The **nogil** (no-GIL) optimization allows 21 performance-critical methods to release Python's Global Interpreter Lock (GIL) during execution, enabling true parallel execution and minimizing Python overhead.

**Performance Impact**: Achieves 60k+ req/sec (6-37x faster than pure Python frameworks)

How It Works
------------

When ``USE_NOGIL=1`` (default), critical operations release the GIL:

.. code-block:: python

    # With nogil optimization
    manager.poll(100)  # Releases GIL - other threads can execute

    # Network operations release GIL
    conn.send(data)    # Releases GIL during C call
    conn.reply(...)    # Releases GIL during C call

Methods with nogil
------------------

The following 21 methods release the GIL for parallel execution:

**Network Operations:**

- ``send()``
- ``close()``
- ``resolve()``
- ``resolve_cancel()``

**WebSocket:**

- ``ws_send()``
- ``ws_upgrade()``

**MQTT:**

- ``mqtt_pub()``
- ``mqtt_sub()``
- ``mqtt_ping()``
- ``mqtt_pong()``
- ``mqtt_disconnect()``

**HTTP:**

- ``reply()``
- ``serve_dir()``
- ``serve_file()``
- ``http_chunk()``
- ``http_sse()``

**TLS:**

- ``tls_init()``
- ``tls_free()``

**Utilities:**

- ``sntp_request()``
- ``http_basic_auth()``
- ``error()``

**Properties:**

- ``local_addr``
- ``remote_addr``

**Thread-safe:**

- ``Manager.wakeup()``

Checking nogil Status
----------------------

At startup, cymongoose prints:

.. code-block:: text

    USE_NOGIL=1  # nogil enabled
    USE_NOGIL=0  # nogil disabled

Build Configuration
-------------------

Enable/Disable
~~~~~~~~~~~~~~

.. code-block:: bash

    # Enable nogil (default)
    pip install -e .

    # Disable nogil
    USE_NOGIL=0 pip install -e .

Rebuild After Changes
~~~~~~~~~~~~~~~~~~~~~

.. code-block:: bash

    # Force recompilation
    rm src/cymongoose/_mongoose.c
    pip install -e . --force-reinstall

Performance Comparison
----------------------

Benchmark results (Apple Silicon, ``wrk -t4 -c100 -d10s``):

.. list-table::
   :header-rows: 1

   * - Configuration
     - Req/sec
     - Performance
   * - nogil enabled
     - 60,973
     - 100% (baseline)
   * - nogil disabled
     - ~35,000
     - ~57% (slower)
   * - Pure Python (aiohttp)
     - 42,452
     - ~70%

Thread Safety
-------------

Mongoose TLS Compatibility
~~~~~~~~~~~~~~~~~~~~~~~~~~~

nogil works safely with Mongoose's built-in TLS because:

1. TLS operations are event-loop based (no background threads)
2. No internal locks in Mongoose TLS implementation
3. All TLS state is per-connection (no shared state)

.. code-block:: python

    # Safe: TLS + nogil
    def handler(conn, ev, data):
        if ev == MG_EV_ACCEPT:
            opts = TlsOpts(cert=cert, key=key)
            conn.tls_init(opts)  # Releases GIL safely

Signal Handling
~~~~~~~~~~~~~~~

With nogil, ``KeyboardInterrupt`` may be delayed during ``poll()``:

.. code-block:: python

    # DON'T rely on try/except for Ctrl+C
    try:
        while True:
            manager.poll(100)  # GIL released - signals deferred
    except KeyboardInterrupt:
        pass  # May not catch reliably

    # DO use signal handlers
    shutdown_requested = False

    def signal_handler(sig, frame):
        global shutdown_requested
        shutdown_requested = True

    signal.signal(signal.SIGINT, signal_handler)

    while not shutdown_requested:
        manager.poll(100)

Memory Lifetime
~~~~~~~~~~~~~~~

Python objects remain valid during nogil C calls:

.. code-block:: python

    # Safe: bytes object stays alive
    data = b"Hello"
    conn.send(data)  # Pointer to data.buf is valid during nogil

Implementation Details
----------------------

Cython Code
~~~~~~~~~~~

.. code-block:: cython

    # With nogil
    IF USE_NOGIL:
        with nogil:
            result = mg_send(conn, buf, length)
    ELSE:
        result = mg_send(conn, buf, length)

All Mongoose C functions must be declared with ``nogil`` in ``mongoose.pxd``:

.. code-block:: cython

    cdef extern from "mongoose.h":
        bint mg_send(mg_connection *conn, const void *buf, size_t len) nogil

Best Practices
--------------

1. **Keep nogil enabled** for production (default)
2. **Use signal handlers** for Ctrl+C, not try/except
3. **Don't access Python objects** from background threads without GIL
4. **Verify nogil at startup** (check USE_NOGIL=1 message)
5. **Benchmark** with nogil on/off to measure impact

Troubleshooting
---------------

nogil Not Working
~~~~~~~~~~~~~~~~~

Check startup message:

.. code-block:: text

    USE_NOGIL=1  # Working
    USE_NOGIL=0  # Not enabled

Rebuild if needed:

.. code-block:: bash

    rm src/cymongoose/_mongoose.c
    pip install -e . --force-reinstall

Performance Lower Than Expected
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

1. Verify nogil is enabled (USE_NOGIL=1)
2. Check poll timeout (use 100ms, not 5000ms)
3. Ensure TLS is needed (disable if not: USE_TLS=0)
4. Run benchmarks to compare

See Also
--------

- :doc:`performance` - Performance tuning guide
- :doc:`threading` - Multi-threading patterns
- :doc:`shutdown` - Signal handling best practices
