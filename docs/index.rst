cymongoose: Python Bindings for the Mongoose Networking Library
===============================================================

.. image:: https://img.shields.io/pypi/v/cymongoose.svg
   :target: https://pypi.org/project/cymongoose/
   :alt: PyPI version

.. image:: https://img.shields.io/pypi/pyversions/cymongoose.svg
   :target: https://pypi.org/project/cymongoose/
   :alt: Python versions

**cymongoose** is a high-performance Cython-based Python wrapper around the `Mongoose <https://github.com/cesanta/mongoose>`_ embedded networking library. It provides Pythonic bindings to Mongoose's comprehensive networking capabilities with C-level performance.

Key Features
------------

- **High Performance**: Achieves 60k+ req/sec with nogil optimization (6-37x faster than pure Python frameworks)
- **Comprehensive Protocol Support**: HTTP/HTTPS, WebSocket/WSS, MQTT/MQTTS, TCP/UDP, DNS, SNTP
- **TLS/SSL Support**: Full certificate-based encryption for all protocols
- **Production Ready**: Signal handling, graceful shutdown, connection draining
- **Zero-copy Design**: Efficient memory usage with view objects over C structs
- **Thread-safe Operations**: 21 methods with GIL release for true parallel execution
- **Pythonic API**: Clean, intuitive interface with comprehensive type hints

Quick Example
-------------

.. code-block:: python

    import signal
    from cymongoose import Manager, MG_EV_HTTP_MSG

    shutdown_requested = False

    def signal_handler(sig, frame):
        global shutdown_requested
        shutdown_requested = True

    def handler(conn, ev, data):
        if ev == MG_EV_HTTP_MSG:
            conn.reply(200, b'{"status": "ok"}')
            conn.drain()  # Graceful close

    def main():
        global shutdown_requested

        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)

        manager = Manager(handler)
        manager.listen('http://0.0.0.0:8000', http=True)

        print("Server running on http://0.0.0.0:8000")
        try:
            while not shutdown_requested:
                manager.poll(100)
            print("Shutting down...")
        finally:
            manager.close()
            print("Server stopped cleanly")

    if __name__ == "__main__":
        main()

Performance Benchmarks
---------------------

Benchmarked with ``wrk -t4 -c100 -d10s`` on an M1 Macbook Air laptop:

.. list-table::
   :header-rows: 1
   :widths: 30 20 20 30

   * - Framework
     - Req/sec
     - Latency (avg)
     - vs cymongoose
   * - **cymongoose**
     - **60,973**
     - **1.67ms**
     - **baseline**
   * - aiohttp
     - 42,452
     - 2.56ms
     - 1.44x slower
   * - FastAPI/uvicorn
     - 9,989
     - 9.96ms
     - 6.1x slower
   * - Flask (threaded)
     - 1,627
     - 22.15ms
     - 37.5x slower

Documentation Contents
----------------------

.. toctree::
   :maxdepth: 2
   :caption: Getting Started

   installation
   quickstart
   examples

.. toctree::
   :maxdepth: 2
   :caption: User Guide

   guide/index
   guide/http
   guide/websocket
   guide/mqtt
   guide/network
   guide/tls

.. toctree::
   :maxdepth: 2
   :caption: API Reference

   api/index
   api/manager
   api/connection
   api/messages
   api/utilities

.. toctree::
   :maxdepth: 2
   :caption: Advanced Topics

   advanced/nogil
   advanced/performance
   advanced/threading
   advanced/shutdown
   advanced/troubleshooting

.. toctree::
   :maxdepth: 1
   :caption: Development

   dev/index
   dev/contributing
   changelog

Indices and Tables
------------------

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`

Project Links
-------------

- **GitHub**: https://github.com/your-username/cymongoose
- **PyPI**: https://pypi.org/project/cymongoose/
- **Issue Tracker**: https://github.com/your-username/cymongoose/issues
- **Mongoose Library**: https://github.com/cesanta/mongoose

License
-------

This project is licensed under the MIT License - see the LICENSE file for details.

The Mongoose library is licensed under GPLv2 or commercial license.
