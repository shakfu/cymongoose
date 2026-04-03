# cymongoose

Python bindings for the Mongoose embedded networking library, built with Cython.

## Overview

**cymongoose** provides Pythonic access to [Mongoose](https://github.com/cesanta/mongoose), a lightweight embedded networking library written in C. It supports HTTP servers, WebSocket, TCP/UDP sockets, and more through a clean, event-driven API.

**[Documentation](https://shakfu.github.io/cymongoose/)** | **[API Reference](https://shakfu.github.io/cymongoose/api/)** | **[Examples](https://shakfu.github.io/cymongoose/examples/)**

## Features

- **HTTP/HTTPS, WebSocket/WSS, MQTT/MQTTS** -- full protocol support with TLS
- **TCP/UDP, DNS, SNTP** -- raw sockets and network utilities
- **Timers** -- periodic callbacks with thread-safe cancellation
- **Event-driven** -- non-blocking I/O with a simple event loop
- **GIL-free** -- 24 methods release the GIL for true parallel execution
- **High performance** -- 60k+ req/sec (6-37x faster than pure Python frameworks)
- **WSGI support** -- serve Flask, Django, Bottle apps on the C event loop
- **Asyncio support** -- `AsyncManager` for asyncio integration
- **Type hints** -- full `.pyi` stubs and `py.typed` marker

## Installation

```sh
pip install cymongoose
```

From source:

```sh
git clone https://github.com/shakfu/cymongoose
cd cymongoose
make
```

Requires Python 3.10+, CMake 3.15+, Cython 3.0+, and a C compiler.

## Quick Start

```python
from cymongoose import Manager, MG_EV_HTTP_MSG

def handler(conn, event, data):
    if event == MG_EV_HTTP_MSG:
        conn.reply(200, "Hello, World!")

mgr = Manager(handler)
mgr.listen("http://127.0.0.1:8000")
mgr.run()
```

More examples:

```python
# Serve static files
def handler(conn, event, data):
    if event == MG_EV_HTTP_MSG:
        conn.serve_dir(data, root_dir="./public")

# WebSocket echo
from cymongoose import MG_EV_WS_MSG

def handler(conn, event, data):
    if event == MG_EV_HTTP_MSG:
        conn.ws_upgrade(data)
    elif event == MG_EV_WS_MSG:
        conn.ws_send(data.text)

# Per-listener handlers on different ports
mgr = Manager()
mgr.listen("http://127.0.0.1:8080", handler=api_handler)
mgr.listen("http://127.0.0.1:8090", handler=web_handler)
mgr.run()
```

### WSGI Framework Support

Run existing Flask/Django/Bottle apps on cymongoose:

```python
from cymongoose.wsgi import serve
from myapp import app  # any WSGI application

serve(app, "http://127.0.0.1:8000", workers=8)
```

See the [quickstart guide](https://shakfu.github.io/cymongoose/quickstart/) and [examples](https://shakfu.github.io/cymongoose/examples/) for more.

## Testing

```sh
make test           # Run all tests (366 tests)
make test-asan      # Run with AddressSanitizer (memory safety)
make qa             # Run tests + lint + type check + format
```

## Development

```sh
make build          # Rebuild the Cython extension
make clean          # Remove build artifacts
make docs-serve     # Serve documentation locally
make help           # Show all available targets
```

## License

Licensed under **GPL-2.0-or-later**, matching the [Mongoose C library](https://github.com/cesanta/mongoose) license. See [LICENSE](LICENSE) for details.

For proprietary use, a [commercial Mongoose license](https://mongoose.ws/licensing/) from Cesanta is required.

## Links

- [Documentation](https://shakfu.github.io/cymongoose/)
- [Mongoose Documentation](https://mongoose.ws/)
- [GitHub Repository](https://github.com/shakfu/cymongoose)
