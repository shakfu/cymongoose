Multi-Threading Guide
=====================

This guide covers thread-safe patterns for multi-threaded cymongoose applications.

Overview
--------

cymongoose supports multi-threading through the ``wakeup()`` mechanism, which allows background worker threads to communicate with the event loop thread safely.

**Use Cases:**

- Offload CPU-intensive work
- Background database queries
- File I/O operations
- External API calls

Basic Pattern
-------------

.. code-block:: python

    import threading
    import queue
    from cymongoose import Manager, MG_EV_HTTP_MSG, MG_EV_WAKEUP

    # Enable wakeup support
    manager = Manager(handler, enable_wakeup=True)

    # Work queues
    work_queue = queue.Queue()
    result_queue = queue.Queue()

    def worker():
        """Background worker thread."""
        while True:
            work = work_queue.get()
            if work is None:
                break

            # Process work
            result = expensive_computation(work['data'])

            # Store result
            result_queue.put({
                'conn_id': work['conn_id'],
                'result': result,
            })

            # Wake up event loop
            manager.wakeup(work['conn_id'], b"result_ready")

    # Start worker
    worker_thread = threading.Thread(target=worker, daemon=True)
    worker_thread.start()

    def handler(conn, ev, data):
        if ev == MG_EV_HTTP_MSG:
            # Offload to worker
            work_queue.put({
                'conn_id': conn.id,  # Use ID, not Connection object
                'data': data.body_bytes,
            })

        elif ev == MG_EV_WAKEUP:
            # Result ready
            result = result_queue.get()
            conn.reply(200, result['result'])
            conn.drain()

Complete Example
----------------

Image Processing Server
~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: python

    import threading
    import queue
    import time
    from cymongoose import Manager, MG_EV_HTTP_MSG, MG_EV_WAKEUP

    # Connection tracking
    connections = {}  # {conn_id: conn}

    # Work queues
    work_queue = queue.Queue()
    result_queue = queue.Queue()

    def process_image(image_data):
        """Simulate expensive image processing."""
        time.sleep(2)  # CPU-intensive work
        return b"PROCESSED_" + image_data

    def worker():
        """Background image processor."""
        while True:
            work = work_queue.get()
            if work is None:
                break

            try:
                result = process_image(work['data'])
                result_queue.put({
                    'conn_id': work['conn_id'],
                    'result': result,
                    'error': None,
                })
            except Exception as e:
                result_queue.put({
                    'conn_id': work['conn_id'],
                    'result': None,
                    'error': str(e),
                })

            # Wake up event loop
            manager.wakeup(work['conn_id'], b"processed")

    def handler(conn, ev, data):
        if ev == MG_EV_HTTP_MSG:
            # Track connection
            connections[conn.id] = conn

            # Offload to worker
            work_queue.put({
                'conn_id': conn.id,
                'data': data.body_bytes,
            })

        elif ev == MG_EV_WAKEUP:
            # Result ready
            result = result_queue.get()

            # Look up connection
            conn = connections.get(result['conn_id'])
            if conn:
                if result['error']:
                    conn.reply(500, result['error'].encode())
                else:
                    conn.reply(200, result['result'])
                conn.drain()

                # Clean up
                del connections[conn.id]

    # Create manager with wakeup support
    manager = Manager(handler, enable_wakeup=True)

    # Start worker threads
    num_workers = 4
    for _ in range(num_workers):
        t = threading.Thread(target=worker, daemon=True)
        t.start()

    manager.listen('http://0.0.0.0:8000', http=True)

    while True:
        manager.poll(100)

Thread Safety Rules
-------------------

1. Pass Connection IDs, Not Objects
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: python

    # Bad: Pass connection object to thread
    work_queue.put({'conn': conn})  # UNSAFE!

    # Good: Pass connection ID
    work_queue.put({'conn_id': conn.id})  # Safe

2. Wakeup Data Must Be Bytes
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: python

    # Bad: String
    manager.wakeup(conn_id, "hello")  # ERROR!

    # Good: Bytes
    manager.wakeup(conn_id, b"hello")  # OK

3. Track Connections
~~~~~~~~~~~~~~~~~~~~

.. code-block:: python

    # Store connections by ID
    connections = {}

    def handler(conn, ev, data):
        if ev == MG_EV_ACCEPT or ev == MG_EV_HTTP_MSG:
            connections[conn.id] = conn

        elif ev == MG_EV_CLOSE:
            if conn.id in connections:
                del connections[conn.id]

        elif ev == MG_EV_WAKEUP:
            # Look up by ID
            if conn.id in connections:
                process_result(conn)

4. Use Queue for Communication
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: python

    import queue

    # Thread-safe queues
    work_queue = queue.Queue()
    result_queue = queue.Queue()

    # Don't use lists or dicts without locks

Multiple Worker Pools
---------------------

Different workers for different tasks:

.. code-block:: python

    db_queue = queue.Queue()
    file_queue = queue.Queue()
    compute_queue = queue.Queue()

    def db_worker():
        while True:
            work = db_queue.get()
            # Database operations

    def file_worker():
        while True:
            work = file_queue.get()
            # File I/O

    def compute_worker():
        while True:
            work = compute_queue.get()
            # CPU-intensive work

    # Start different worker pools
    for _ in range(2):
        threading.Thread(target=db_worker, daemon=True).start()

    for _ in range(4):
        threading.Thread(target=compute_worker, daemon=True).start()

    def handler(conn, ev, data):
        if ev == MG_EV_HTTP_MSG:
            if data.uri.startswith("/db/"):
                db_queue.put(...)
            elif data.uri.startswith("/compute/"):
                compute_queue.put(...)

Fast Path vs Slow Path
----------------------

Handle simple requests immediately, offload complex ones:

.. code-block:: python

    def handler(conn, ev, data):
        if ev == MG_EV_HTTP_MSG:
            # Fast path: simple request
            if data.uri == "/status":
                conn.reply(200, b'{"status": "ok"}')
                conn.drain()

            # Slow path: complex request
            elif data.uri == "/process":
                connections[conn.id] = conn
                work_queue.put({
                    'conn_id': conn.id,
                    'data': data.body_bytes,
                })

Graceful Shutdown
-----------------

Stop workers cleanly:

.. code-block:: python

    shutdown_requested = False

    def signal_handler(sig, frame):
        global shutdown_requested
        shutdown_requested = True

        # Stop workers
        for _ in range(num_workers):
            work_queue.put(None)  # Poison pill

    signal.signal(signal.SIGINT, signal_handler)

    # Main loop
    while not shutdown_requested:
        manager.poll(100)

    # Wait for workers
    for thread in worker_threads:
        thread.join(timeout=5.0)

    manager.close()

Best Practices
--------------

1. **Enable wakeup** when creating Manager
2. **Pass conn.id** to threads, not Connection objects
3. **Use thread-safe queues** for communication
4. **Track connections** by ID in a dict
5. **Clean up** on MG_EV_CLOSE
6. **Limit worker count** (2-4x CPU cores)
7. **Handle errors** in worker threads
8. **Implement timeouts** to prevent hangs

See Also
--------

- :doc:`nogil` - GIL-free performance
- :doc:`performance` - Performance optimization
- :doc:`shutdown` - Graceful shutdown patterns
