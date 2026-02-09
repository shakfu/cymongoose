# cymongoose

Python bindings for the Mongoose embedded networking library, built with Cython.

## Overview

**cymongoose** provides Pythonic access to [Mongoose](https://github.com/cesanta/mongoose), a lightweight embedded networking library written in C. It supports HTTP servers, WebSocket, TCP/UDP sockets, and more through a clean, event-driven API.

## Features

### Core Protocols

- **HTTP/HTTPS**: Server and client with TLS support, chunked transfer encoding, SSE
- **WebSocket/WSS**: Full WebSocket support with text/binary frames over TLS
- **MQTT/MQTTS**: Publish/subscribe messaging with QoS support
- **TCP/UDP**: Raw socket support with custom protocols
- **DNS**: Asynchronous hostname resolution
- **SNTP**: Network time synchronization

### Advanced Features

- **TLS/SSL**: Certificate-based encryption with custom CA support
- **Timers**: Periodic callbacks with precise timing control
- **Flow Control**: Backpressure handling and buffer management
- **Authentication**: HTTP Basic Auth, MQTT credentials
- **JSON Parsing**: Built-in JSON extraction utilities
- **URL Encoding**: Safe URL parameter encoding

### Technical

- **Event-driven**: Non-blocking I/O with a simple event loop
- **Low overhead**: Thin Cython wrapper over native C library
- **Python 3.10+**: Modern Python with type hints
- **Comprehensive**: 244 tests, 100% pass rate
- **Production Examples**: 17 complete examples from Mongoose tutorials
- **TLS Support**: Built-in TLS/SSL encryption (MG_TLS_BUILTIN)
- **GIL Optimization**: 21 methods release GIL for true parallel execution
- **High Performance**: 60k+ req/sec (6-37x faster than pure Python frameworks)

## Installation

### From pypi

```sh
pip install cymongoose
```

### From source

```sh
# Clone the repository
git clone https://github.com/shakfu/cymongoose
cd cymongoose
make
```

Also type `make help` gives you a list of commands

### Requirements

- Python 3.10 or higher
- CMake 3.15+
- Cython 3.0+
- C compiler (gcc, clang, or MSVC)

## Quick Start

> **Note:** These examples bind to `127.0.0.1` (localhost only). For production, use `0.0.0.0` to listen on all interfaces.

### Simple HTTP Server

```python
from cymongoose import Manager, MG_EV_HTTP_MSG

def handler(conn, event, data):
    if event == MG_EV_HTTP_MSG:
        conn.reply(200, "Hello, World!")

mgr = Manager(handler)
mgr.listen("http://127.0.0.1:8000", http=True)
print("Server running on http://localhost:8000. Press Ctrl+C to stop.")
mgr.run()
```

### Serve Static Files

```python
from cymongoose import Manager, MG_EV_HTTP_MSG

def handler(conn, event, data):
    if event == MG_EV_HTTP_MSG:
        conn.serve_dir(data, root_dir="./public")

mgr = Manager(handler)
mgr.listen("http://127.0.0.1:8000", http=True)
mgr.run()
```

### WebSocket Echo Server

```python
from cymongoose import Manager, MG_EV_HTTP_MSG, MG_EV_WS_MSG

def handler(conn, event, data):
    if event == MG_EV_HTTP_MSG:
        conn.ws_upgrade(data)  # Upgrade HTTP to WebSocket
    elif event == MG_EV_WS_MSG:
        conn.ws_send(data.text)  # Echo back

mgr = Manager(handler)
mgr.listen("http://127.0.0.1:8000", http=True)
mgr.run()
```

### Per-Listener Handlers (new)

Run different handlers on different ports. Accepted connections automatically inherit the handler from their listener:

```python
from cymongoose import Manager, MG_EV_HTTP_MSG

def api_handler(conn, event, data):
    if event == MG_EV_HTTP_MSG:
        conn.reply(200, '{"status":"ok"}', {"Content-Type": "application/json\r\n"})

def web_handler(conn, event, data):
    if event == MG_EV_HTTP_MSG:
        conn.serve_dir(data, root_dir="./public")

mgr = Manager()  # no default handler needed
mgr.listen("http://127.0.0.1:8080", handler=api_handler, http=True)
mgr.listen("http://127.0.0.1:8090", handler=web_handler, http=True)
mgr.run()
```

## Examples

The project includes several complete examples translated from Mongoose C tutorials:

### Core HTTP/WebSocket

- **HTTP Server** - Static files, TLS, multipart uploads, REST API
- **HTTP Client** - GET/POST, TLS, timeouts, custom headers
- **WebSocket Server** - Echo, mixed HTTP+WS, client tracking
- **WebSocket Broadcasting** - Timer-based broadcasts to multiple clients

### MQTT

- **MQTT Client** - Pub/sub, QoS, reconnection, keepalive
- **MQTT Broker** - Message routing, topic matching, subscriptions

### Specialized HTTP

- **HTTP Streaming** - Chunked transfer encoding, large responses
- **HTTP File Upload** - Disk streaming, multipart forms
- **RESTful Server** - JSON API, CRUD operations, routing
- **Server-Sent Events** - Real-time push updates

### Network Protocols

- **SNTP Client** - Network time sync over UDP
- **DNS Client** - Async hostname resolution
- **TCP Echo Server** - Raw TCP sockets, custom protocols
- **UDP Echo Server** - Connectionless datagrams

### Advanced Features

- **TLS HTTPS Server** - Certificate-based encryption, SNI
- **HTTP Proxy Client** - CONNECT method tunneling
- **Multi-threaded Server** - Background workers, `Manager.wakeup()`

**All examples include:**

- Production-ready patterns (signal handlers, graceful shutdown)
- Command-line arguments for flexibility
- Comprehensive test coverage (42 tests)
- Detailed documentation with C tutorial references

See `tests/examples/README.md` for usage instructions and `tests/examples/` for source code.

## API Reference

### Manager

The main event loop manager.

```python
mgr = Manager(handler=None, enable_wakeup=False)
```

**Core Methods:**

- `poll(timeout_ms=0)` - Run one iteration of the event loop
- `run(poll_ms=100)` - Run the event loop until SIGINT/SIGTERM, then close
- `listen(url, handler=None)` - Create a listening socket (handler is inherited by accepted children)
- `connect(url, handler=None)` - Create an outbound connection
- `close()` - Free resources

**Protocol-Specific:**

- `http_listen(url, handler=None)` - Create HTTP server
- `http_connect(url, handler=None)` - Create HTTP client
- `ws_connect(url, handler=None)` - WebSocket client
- `mqtt_connect(url, handler=None, client_id, username, password, ...)` - MQTT client
- `mqtt_listen(url, handler=None)` - MQTT broker
- `sntp_connect(url, handler=None)` - SNTP time client
- `timer_add(milliseconds, callback, repeat=False, run_now=False)` - Add periodic timer
- `wakeup(connection_id, data)` - Wake connection from another thread

### Connection

Represents a network connection.

```python
# Send data
conn.send(data)                    # Raw bytes
conn.reply(status, body, headers)  # HTTP response
conn.ws_upgrade(message)           # Upgrade HTTP to WebSocket
conn.ws_send(data, op)             # WebSocket frame

# HTTP
conn.serve_dir(message, root_dir)  # Serve static files
conn.serve_file(message, path)     # Serve single file
conn.http_chunk(data)              # Send chunked data
conn.http_sse(event_type, data)    # Server-Sent Events
conn.http_basic_auth(user, pass_)  # HTTP Basic Auth

# MQTT
conn.mqtt_pub(topic, message, ..)  # Publish an MQTT message
conn.mqtt_sub(topic, qos=0)        # Subscribe to an MQTT topic
conn.mqtt_ping()                   # Send MQTT ping
conn.mqtt_pong()                   # Send MQTT pong
conn.mqtt_disconnect()             # Send MQTT disconnect message

# SNTP
conn.sntp_request()                # Request time

# TLS
conn.tls_init(TlsOpts(...))        # Initialize TLS
conn.tls_free()                    # Free TLS resources

# DNS
conn.resolve(url)                  # Async DNS lookup
conn.resolve_cancel()              # Cancel DNS lookup

# Connection management
conn.drain()                       # Graceful close (flush buffer first)
conn.close()                       # Immediate close
conn.error(message)                # Trigger error event

# Properties
conn.is_listening                  # Listener socket?
conn.is_websocket                  # WebSocket connection?
conn.is_tls                        # TLS/SSL enabled?
conn.is_udp                        # UDP socket?
conn.is_readable                   # Data available?
conn.is_writable                   # Can write?
conn.is_full                       # Buffer full? (backpressure)
conn.is_draining                   # Draining before close?
conn.id                            # Connection ID
conn.handler                       # Current handler
conn.set_handler(fn)               # Set handler (propagates to children if listener)
conn.userdata                      # Custom Python object
conn.local_addr                    # (ip, port) tuple
conn.remote_addr                   # (ip, port) tuple

# Buffer access
conn.recv_len                      # Bytes in receive buffer
conn.send_len                      # Bytes in send buffer
conn.recv_size                     # Receive buffer capacity
conn.send_size                     # Send buffer capacity
conn.recv_data(n)                  # Read from receive buffer
conn.send_data(n)                  # Read from send buffer
```

### TlsOpts

TLS/SSL configuration.

```python
opts = TlsOpts(
    ca=None,                       # CA certificate (PEM)
    cert=None,                     # Server/client certificate (PEM)
    key=None,                      # Private key (PEM)
    name=None,                     # Server name (SNI)
    skip_verification=False        # Skip cert validation (dev only!)
)
```

### HttpMessage

HTTP request/response view.

```python
msg.method                         # "GET", "POST", etc.
msg.uri                            # "/path"
msg.query                          # "?key=value"
msg.proto                          # "HTTP/1.1"
msg.body_text                      # Body as string
msg.body_bytes                     # Body as bytes
msg.header("Name")                 # Get header value
msg.headers()                      # All headers as list of tuples
msg.query_var("key")               # Extract query parameter
msg.status()                       # HTTP status code
msg.header_var(header, var)        # Extract variable from header
```

### WsMessage

WebSocket frame data.

```python
ws.text                            # Frame data as string
ws.data                            # Frame data as bytes
ws.flags                           # WebSocket flags
```

### MqttMessage

MQTT message data.

```python
mqtt.topic                         # Topic as string
mqtt.data                          # Payload as bytes
mqtt.id                            # Message ID
mqtt.cmd                           # MQTT command
mqtt.qos                           # Quality of Service (0-2)
mqtt.ack                           # Acknowledgment flag
```

### Event Constants

```python
# Core events
MG_EV_ERROR                        # Error occurred
MG_EV_OPEN                         # Connection created
MG_EV_POLL                         # Poll iteration
MG_EV_RESOLVE                      # DNS resolution complete
MG_EV_CONNECT                      # Outbound connection established
MG_EV_ACCEPT                       # Inbound connection accepted
MG_EV_TLS_HS                       # TLS handshake complete
MG_EV_READ                         # Data available to read
MG_EV_WRITE                        # Data written
MG_EV_CLOSE                        # Connection closed

# Protocol events
MG_EV_HTTP_MSG                     # HTTP message received
MG_EV_WS_OPEN                      # WebSocket handshake complete
MG_EV_WS_MSG                       # WebSocket message received
MG_EV_MQTT_CMD                     # MQTT command received
MG_EV_MQTT_MSG                     # MQTT message received
MG_EV_MQTT_OPEN                    # MQTT connection established
MG_EV_SNTP_TIME                    # SNTP time received
MG_EV_WAKEUP                       # Wakeup notification
```

### Utility Functions

```python
# JSON parsing
json_get(json_str, "$.path")           # Get JSON value
json_get_num(json_str, "$.number")     # Get as number
json_get_bool(json_str, "$.bool")      # Get as boolean
json_get_long(json_str, "$.int", default=0)  # Get as long
json_get_str(json_str, "$.string")     # Get as string

# URL encoding
url_encode(data)                       # Encode for URL

# Multipart forms
http_parse_multipart(body, offset=0)   # Parse multipart data
```

## Testing

The project includes a comprehensive test suite with **244 tests** (100% passing):

### Test Coverage by Feature

**Core Functionality (168 tests):**

- **HTTP/HTTPS**: Server, client, headers, query params, chunked encoding, SSE (40 tests)
- **WebSocket**: Handshake, text/binary frames, opcodes (10 tests)
- **MQTT**: Connect, publish, subscribe, ping/pong, disconnect (11 tests)
- **TLS/SSL**: Configuration, initialization, properties (12 tests)
- **Timers**: Single-shot, repeating, callbacks, cleanup (10 tests)
- **DNS**: Resolution, cancellation (4 tests)
- **SNTP**: Time requests, format validation (5 tests)
- **JSON**: Parsing, type conversion, nested access (9 tests)
- **Buffer Access**: Direct buffer inspection, flow control (10 tests)
- **Connection State**: Lifecycle, properties, events (15+ tests)
- **Security**: HTTP Basic Auth, TLS properties (6 tests)
- **Utilities**: URL encoding, multipart forms, wakeup (10 tests)
- **Flow Control**: Drain, backpressure (4 tests)

**Example Tests:**

- HTTP/WebSocket examples
- MQTT examples
- Specialized HTTP examples
- Network protocols
- Advanced features
- README example validation
- WebSocket broadcast examples

### Running Tests

```sh
make test                                          # Run all tests (244 tests)
uv run python -m pytest tests/ -v                  # Verbose output
uv run python -m pytest tests/test_http_server.py  # Run specific file
uv run python -m pytest tests/ -k "test_timer"     # Run matching tests
uv run python -m pytest tests/examples/            # Run example tests only
```

### Test Infrastructure

- Dynamic port allocation prevents conflicts
- Background polling threads for async operations
- Proper cleanup in finally blocks
- 100% pass rate (244/244 tests passing)
- WebSocket tests require `websocket-client` (`uv add --dev websocket-client`)

### Memory Safety Testing

AddressSanitizer (ASAN) support is available for detecting memory errors:

```sh
make build-asan                        # Build with ASAN enabled
make test-asan                         # Run tests with memory error detection
```

This detects use-after-free, buffer overflows, and other memory bugs at runtime.

> **macOS note:** `build-asan` compiles a small helper (`build/run_asan`) that
> injects the ASAN runtime via `DYLD_INSERT_LIBRARIES` before exec'ing Python.
> This is necessary because macOS SIP strips `DYLD_INSERT_LIBRARIES` from
> processes spawned by system binaries (`/usr/bin/make`, `/bin/sh`).

## Development

The project uses [scikit-build-core](https://scikit-build-core.readthedocs.io/) with CMake to build the Cython extension, and [uv](https://docs.astral.sh/uv/) for environment and dependency management.

```sh
make build          # Rebuild the Cython extension
make test           # Run all tests
make clean          # Remove build artifacts
make help           # Show all available targets
```

## Architecture

- **CMake build** (`CMakeLists.txt`): Cythonizes `.pyx` and compiles the extension via scikit-build-core
- **Cython bindings** (`src/cymongoose/_mongoose.pyx`): Python wrapper classes
- **C declarations** (`src/cymongoose/mongoose.pxd`): Cython interface to Mongoose C API
- **Vendored Mongoose** (`thirdparty/mongoose/`): Embedded C library

### Performance Optimization

The wrapper achieves **C-level performance** through aggressive optimization:

**GIL Release (`nogil`):**

- **21 critical methods release GIL** for true parallel execution
- Network: `send()`, `close()`, `resolve()`, `resolve_cancel()`
- WebSocket: `ws_send()`, `ws_upgrade()`
- MQTT: `mqtt_pub()`, `mqtt_sub()`, `mqtt_ping()`, `mqtt_pong()`, `mqtt_disconnect()`
- HTTP: `reply()`, `serve_dir()`, `serve_file()`, `http_chunk()`, `http_sse()`
- TLS: `tls_init()`, `tls_free()`
- Utilities: `sntp_request()`, `http_basic_auth()`, `error()`
- Properties: `local_addr`, `remote_addr`
- Thread-safe: `Manager.wakeup()`

**TLS Compatibility:**

- TLS and `nogil` work together safely
- Mongoose's built-in TLS is event-loop based (no internal locks)
- Both optimizations enabled by default

**Benchmark Results** (Apple Silicon, `wrk -t4 -c100 -d10s`):

- **cymongoose**: 60,973 req/sec (1.67ms latency)
- aiohttp: 42,452 req/sec (1.44x slower)
- FastAPI/uvicorn: 9,989 req/sec (6.1x slower)
- Flask: 1,627 req/sec (37.5x slower)

See `docs/nogil_optimization_summary.md` and `benchmarks/RESULTS.md` for details.

## License

MIT

## Links

- [Mongoose Documentation](https://mongoose.ws/)
- [GitHub Repository](https://github.com/shakfu/cymongoose)
