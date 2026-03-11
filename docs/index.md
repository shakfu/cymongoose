# cymongoose: Python Bindings for the Mongoose Networking Library

[![PyPI version](https://img.shields.io/pypi/v/cymongoose.svg)](https://pypi.org/project/cymongoose/)
[![Python versions](https://img.shields.io/pypi/pyversions/cymongoose.svg)](https://pypi.org/project/cymongoose/)

**cymongoose** is a high-performance Cython-based Python wrapper around
the [Mongoose](https://github.com/cesanta/mongoose) embedded networking
library. It provides Pythonic bindings to Mongoose's comprehensive
networking capabilities with C-level performance.

## Key Features

- **High Performance**: Achieves 60k+ req/sec with nogil optimization
  (6-37x faster than pure Python frameworks)
- **Comprehensive Protocol Support**: HTTP/HTTPS, WebSocket/WSS,
  MQTT/MQTTS, TCP/UDP, DNS, SNTP
- **TLS/SSL Support**: Full certificate-based encryption for all
  protocols
- **Production Ready**: Signal handling, graceful shutdown, connection
  draining
- **Zero-copy Design**: Efficient memory usage with view objects over C
  structs
- **Thread-safe Operations**: 21 methods with GIL release for true
  parallel execution
- **Pythonic API**: Clean, intuitive interface with comprehensive type
  hints

## Quick Example

```python
from cymongoose import Manager, MG_EV_HTTP_MSG

def handler(conn, ev, data):
    if ev == MG_EV_HTTP_MSG:
        conn.reply(200, b'{"status": "ok"}')
        conn.drain()

mgr = Manager(handler)
mgr.listen("http://0.0.0.0:8000")
print("Server running on http://0.0.0.0:8000")
mgr.run()  # Blocks until SIGINT/SIGTERM, then cleans up
```

## Performance Benchmarks

Benchmarked with `wrk -t4 -c100 -d10s` on an M1 Macbook Air laptop:

| Framework | Req/sec | Latency (avg) | vs cymongoose |
|---|---|---|---|
| **cymongoose** | **60,973** | **1.67ms** | **baseline** |
| aiohttp | 42,452 | 2.56ms | 1.44x slower |
| FastAPI/uvicorn | 9,989 | 9.96ms | 6.1x slower |
| Flask (threaded) | 1,627 | 22.15ms | 37.5x slower |

## Project Links

- **GitHub**: <https://github.com/shakfu/cymongoose>
- **PyPI**: <https://pypi.org/project/cymongoose/>
- **Issue Tracker**: <https://github.com/shakfu/cymongoose/issues>
- **Mongoose Library**: <https://github.com/cesanta/mongoose>

## License

This project is licensed under GPL-2.0-or-later, matching the Mongoose
library's open-source license. Commercial licensing is available from
[Cesanta](https://mongoose.ws/) for proprietary use.
