# cymongoose Examples

This directory contains **17 complete, production-ready examples** demonstrating how to use cymongoose for various networking scenarios. Each example is a runnable Python script that translates C tutorials from the Mongoose library.

 **All 17/17 examples complete** with 210 tests passing!

## Table of Contents

- [Core HTTP/WebSocket Examples](#priority-1-core-httpwebsocket-examples)
  - [HTTP Server](#1-http-server-httphttpserverpy)
  - [HTTP Client](#2-http-client-httphttpclientpy)
  - [WebSocket Server](#3-websocket-server-websocketwebsocketserverpy)
  - [WebSocket Timer Broadcasting](#4-websocket-timer-broadcasting-websocketwebsocketbroadcastpy)
- [MQTT Examples](#priority-2-mqtt-examples)
  - [MQTT Client](#5-mqtt-client-mqttmqttclientpy)
  - [MQTT Broker/Server](#6-mqtt-brokerserver-mqttmqttserverpy)
- [Specialized HTTP Features](#priority-3-specialized-http-features)
  - [HTTP Streaming Client](#7-http-streaming-client-httphttpstreamingclientpy)
  - [HTTP File Upload](#8-http-file-upload-httphttpfileuploadpy)
  - [HTTP RESTful Server](#9-http-restful-server-httphttprestfulserverpy)
  - [Server-Sent Events (SSE)](#10-server-sent-events-sse-httphttpsseserverpy)
- [Network Protocols](#priority-4-network-protocols)
  - [SNTP Client](#11-sntp-client-networksntpclientpy)
  - [DNS Resolution Client](#12-dns-resolution-client-networkdnsclientpy)
  - [TCP Echo Server](#13-tcp-echo-server-networktcpechoserverpy)
  - [UDP Echo Server](#14-udp-echo-server-networkudpechoserverpy)
- [Advanced Features](#priority-5-advanced-features)
  - [TLS/SSL HTTPS Server](#15-tlsssl-https-server-advancedtlshttpsserverpy)
  - [HTTP Proxy Client](#16-http-proxy-client-advancedhttpproxyclientpy)
  - [Multi-threaded Server](#17-multi-threaded-server-advancedmultithreadedserverpy)
- [Running the Examples](#running-the-examples)
- [Example Structure](#example-structure)
- [Common Patterns](#common-patterns)
- [Validation Benefits](#validation-benefits)
- [Example Summary](#example-summary)
- [Contributing](#contributing)

---

## Core HTTP/WebSocket Examples

### HTTP Examples

#### 1. HTTP Server (`http/http_server.py`)

Comprehensive HTTP server demonstrating static file serving, TLS, file uploads, and API endpoints.

**Features**:

- Static file serving with `serve_dir()`
- File upload handling with multipart forms
- TLS/SSL configuration with self-signed certificates
- REST API endpoints
- Custom routing

**Usage**:

```bash
# Basic HTTP server on port 8000
python http/http_server.py

# Custom port
python http/http_server.py --port 8080

# HTTPS with self-signed certificate
python http/http_server.py --tls

# Custom web root directory
python http/http_server.py --root ./public
```

**Test**:

```bash
curl http://localhost:8000/
curl http://localhost:8000/api/info
curl -F "file=@README.md" http://localhost:8000/upload
```

**C Tutorial Reference**: `thirdparty/mongoose/tutorials/http/http-server/main.c`

---

#### 2. HTTP Client (`http/http_client.py`)

HTTP client with support for GET/POST requests, TLS, timeouts, and custom headers.

**Features**:

- Simple GET/POST requests
- TLS client configuration with CA certificates
- Connection timeout handling
- Custom headers
- Request/response processing

**Usage**:

```bash
# Simple GET request
python http/http_client.py https://httpbin.org/get

# POST with data
python http/http_client.py https://httpbin.org/post --method POST --data "hello=world"

# With custom headers
python http/http_client.py https://api.github.com/users/shakfu --header "User-Agent: cymongoose"

# With timeout
python http/http_client.py https://example.com --timeout 5

# Verbose output
python http/http_client.py https://httpbin.org/get --verbose
```

**Test**:

```bash
# Test with local server (run http_server.py first)
python http/http_client.py http://localhost:8000/api/info
```

**C Tutorial Reference**: `thirdparty/mongoose/tutorials/http/http-client/main.c`

---

### WebSocket Examples

#### 3. WebSocket Server (`websocket/websocket_server.py`)

WebSocket echo server with REST API and static file serving, demonstrating mixed HTTP+WS server.

**Features**:

- WebSocket upgrade from HTTP
- Echo server pattern (text and binary)
- REST API alongside WebSocket
- Static file serving
- Client tracking
- Interactive HTML interface

**Usage**:

```bash
# Start WebSocket server
python websocket/websocket_server.py

# Custom port
python websocket/websocket_server.py --port 8080

# Custom web root
python websocket/websocket_server.py --root ./public
```

**Test**:

```bash
# Open in browser (includes interactive WebSocket client)
open http://localhost:8000/

# Or test with Python websocket-client
python -c "
from websocket import create_connection
ws = create_connection('ws://localhost:8000/ws')
ws.send('Hello')
print(ws.recv())  # Echo: Hello
ws.close()
"

# Check stats API
curl http://localhost:8000/api/stats

# Broadcast to all clients
curl -X POST -d "Test message" http://localhost:8000/api/broadcast
```

**C Tutorial Reference**: `thirdparty/mongoose/tutorials/websocket/websocket-server/main.c`

---

#### 4. WebSocket Timer Broadcasting (`websocket/websocket_broadcast.py`)

WebSocket server with periodic broadcasting to all connected clients using timers.

**Features**:

- Periodic timer broadcasting to WebSocket clients
- Connection tracking with userdata
- Timer API with `MG_TIMER_REPEAT`
- Broadcasting to multiple connections
- Real-time push updates
- Statistics tracking

**Usage**:

```bash
# Start broadcast server (broadcasts every 1 second)
python websocket/websocket_broadcast.py

# Custom port and interval
python websocket/websocket_broadcast.py --port 8080 --interval 2.5
```

**Test**:

```bash
# Open multiple browser tabs to see synchronized broadcasts
open http://localhost:8000/
open http://localhost:8000/  # Second tab
open http://localhost:8000/  # Third tab

# All tabs will receive periodic broadcast messages
```

**C Tutorial Reference**: `thirdparty/mongoose/tutorials/core/timers/main.c`

---

## MQTT Examples

### 5. MQTT Client (`mqtt/mqtt_client.py`)

MQTT client demonstrating publish/subscribe messaging with QoS, reconnection, and keepalive.

**Features**:

- MQTT connect with QoS, clean session, keepalive
- Subscribe and publish patterns
- Timer-based reconnection logic
- Ping/pong handling for keepalive
- Last will and testament configuration
- Multiple topic subscriptions

**Usage**:

```bash
# Connect to public MQTT broker
python mqtt/mqtt_client.py mqtt://broker.hivemq.com:1883

# Subscribe to topic
python mqtt/mqtt_client.py mqtt://broker.hivemq.com:1883 --subscribe "test/topic"

# Publish message
python mqtt/mqtt_client.py mqtt://broker.hivemq.com:1883 --publish "test/topic" --message "Hello MQTT"

# With QoS and keepalive
python mqtt/mqtt_client.py mqtt://broker.hivemq.com:1883 --qos 1 --keepalive 60
```

**C Tutorial Reference**: `thirdparty/mongoose/tutorials/mqtt/mqtt-client/main.c`

---

### 6. MQTT Broker/Server (`mqtt/mqtt_server.py`)

Basic MQTT broker implementation demonstrating message routing and topic matching.

**Features**:

- MQTT broker functionality
- Topic-based message routing
- Multiple client connections
- Subscription management
- Publish/subscribe pattern enforcement
- Connection tracking

**Usage**:

```bash
# Start MQTT broker on default port 1883
python mqtt/mqtt_server.py

# Custom port
python mqtt/mqtt_server.py --port 1884

# Test with MQTT client
python mqtt/mqtt_client.py mqtt://localhost:1883 --subscribe "test/#"
```

**C Tutorial Reference**: `thirdparty/mongoose/tutorials/mqtt/mqtt-server/main.c`

---

## Specialized HTTP Features

### 7. HTTP Streaming Client (`http/http_streaming_client.py`)

HTTP client demonstrating chunked transfer encoding for streaming responses.

**Features**:

- Chunked transfer encoding for responses
- Streaming large responses without buffering
- Progress tracking during download
- Memory-efficient processing
- Header inspection before body processing

**Usage**:

```bash
# Stream large file
python http/http_streaming_client.py https://httpbin.org/stream/100

# With verbose output
python http/http_streaming_client.py https://httpbin.org/stream/10 --verbose
```

**C Tutorial Reference**: `thirdparty/mongoose/tutorials/http/http-streaming-client/main.c`

---

### 8. HTTP File Upload (`http/http_file_upload.py`)

HTTP server demonstrating file upload handling with streaming to disk.

**Features**:

- Single POST file upload handling
- Streaming uploads to disk without full buffering
- Memory-efficient processing of large files
- Multipart form data parsing
- File metadata extraction (filename, content-type)
- Progress tracking

**Usage**:

```bash
# Start upload server
python http/http_file_upload.py

# Upload file with curl
curl -F "file=@largefile.zip" http://localhost:8000/upload

# Custom upload directory
python http/http_file_upload.py --upload-dir /tmp/uploads
```

**C Tutorial Reference**: `thirdparty/mongoose/tutorials/http/file-upload-single-post/main.c`

---

### 9. HTTP RESTful Server (`http/http_restful_server.py`)

REST API server demonstrating JSON request/response handling and URL routing.

**Features**:

- REST API patterns (GET, POST, PUT, DELETE)
- JSON request/response handling
- URL routing with path parameters
- CRUD operations demonstration
- Content-Type negotiation
- Error responses with proper status codes

**Usage**:

```bash
# Start REST API server
python http/http_restful_server.py

# Test endpoints
curl http://localhost:8000/api/items
curl -X POST -H "Content-Type: application/json" -d '{"name":"test"}' http://localhost:8000/api/items
curl http://localhost:8000/api/items/1
curl -X PUT -H "Content-Type: application/json" -d '{"name":"updated"}' http://localhost:8000/api/items/1
curl -X DELETE http://localhost:8000/api/items/1
```

**C Tutorial Reference**: `thirdparty/mongoose/tutorials/http/http-restful-server/main.c`

---

### 10. Server-Sent Events (SSE) (`http/http_sse_server.py`)

HTTP server demonstrating Server-Sent Events for real-time updates.

**Features**:

- SSE streaming to clients
- Real-time server push updates
- Timer-based event broadcasting
- Multiple concurrent SSE connections
- Event naming and data formatting
- Automatic reconnection handling (client-side)

**Usage**:

```bash
# Start SSE server (broadcasts every 1 second)
python http/http_sse_server.py

# Custom broadcast interval
python http/http_sse_server.py --interval 0.5

# Test with curl
curl http://localhost:8000/events

# Or open in browser
open http://localhost:8000/
```

**C Tutorial Reference**: Device dashboard examples in Mongoose tutorials

---

## Network Protocols

### 11. SNTP Client (`network/sntp_client.py`)

Network time synchronization client using SNTP protocol over UDP.

**Features**:

- Network time synchronization via SNTP
- UDP-based protocol
- Timer-based periodic sync (default: 30 seconds)
- Boot timestamp calculation for embedded systems without RTC
- Uses Google's public time server (time.google.com)
- Unix timestamp conversion

**Usage**:

```bash
# Sync with default server (time.google.com)
python network/sntp_client.py

# Custom SNTP server
python network/sntp_client.py --server time.nist.gov

# Custom sync interval (seconds)
python network/sntp_client.py --interval 60

# One-shot sync (no periodic updates)
python network/sntp_client.py --once
```

**C Tutorial Reference**: `thirdparty/mongoose/tutorials/udp/sntp-time-sync/main.c`

---

### 12. DNS Resolution Client (`network/dns_client.py`)

Asynchronous DNS client demonstrating hostname resolution and cancellation.

**Features**:

- Asynchronous DNS hostname lookups
- DNS resolution cancellation support
- Periodic resolution with timer
- IPv4/IPv6 support
- Timeout handling
- Useful for network diagnostics and monitoring

**Usage**:

```bash
# Resolve hostname once
python network/dns_client.py google.com

# Periodic resolution (every 5 seconds)
python network/dns_client.py google.com --interval 5

# Resolve with port
python network/dns_client.py google.com:443
```

**C Tutorial Reference**: HTTP client examples with custom DNS

---

### 13. TCP Echo Server (`network/tcp_echo_server.py`)

Raw TCP socket server/client demonstrating custom protocol implementation.

**Features**:

- Raw TCP socket handling (no HTTP layer)
- Server echoes received data back to client
- Client with timer-based reconnection (15 seconds)
- Custom protocol implementation over TCP
- Useful for learning raw socket programming
- Demonstrates MG_EV_ACCEPT and MG_EV_READ events

**Usage**:

```bash
# Start TCP echo server
python network/tcp_echo_server.py

# Custom port
python network/tcp_echo_server.py --port 9000

# Test with telnet
telnet localhost 8000

# Or netcat
nc localhost 8000
```

**C Tutorial Reference**: `thirdparty/mongoose/tutorials/tcp/tcp/main.c`

---

### 14. UDP Echo Server (`network/udp_echo_server.py`)

UDP socket server/client demonstrating connectionless protocol.

**Features**:

- UDP connectionless protocol demonstration
- Server echoes datagrams back to sender
- Client sends periodic datagrams
- Key differences from TCP explained in docstring
- Datagram handling without connection state
- Useful for understanding UDP vs TCP

**Usage**:

```bash
# Start UDP echo server
python network/udp_echo_server.py

# Custom port
python network/udp_echo_server.py --port 9001

# Test with netcat
nc -u localhost 8000
```

**C Tutorial Reference**: UDP examples in Mongoose tutorials

---

## Advanced Features

### 15. TLS/SSL HTTPS Server (`advanced/tls_https_server.py`)

HTTPS server with TLS/SSL certificate-based encryption.

**Features**:

- TLS/SSL certificate-based encryption for HTTPS
- Self-signed certificates embedded for development
- Command-line arguments for custom certificates (--cert, --key, --ca)
- Skip verification flag for testing (--skip-verify)
- Multiple secure endpoints (/, /api/status, /api/echo)
- Server Name Indication (SNI) support

**Usage**:

```bash
# Development mode with self-signed certificate
python advanced/tls_https_server.py --skip-verify

# Custom port
python advanced/tls_https_server.py --listen https://0.0.0.0:8443 --skip-verify

# Production mode with real certificates
python advanced/tls_https_server.py --cert server.pem --key server.key

# With CA certificate
python advanced/tls_https_server.py --cert server.pem --key server.key --ca ca.pem

# Test with curl
curl -k https://localhost:8443/
curl -k https://localhost:8443/api/status
```

**C Tutorial Reference**: `thirdparty/mongoose/tutorials/tls/` examples

---

### 16. HTTP Proxy Client (`advanced/http_proxy_client.py`)

HTTP client that uses a proxy server with CONNECT method tunneling.

**Features**:

- HTTP CONNECT method for proxy tunneling
- Two-stage connection pattern (client → proxy → target)
- TLS initialization after tunnel establishment
- URL parsing utility function
- Proxy authentication support (headers)
- Works with HTTP and HTTPS proxies

**Usage**:

```bash
# Connect through HTTP proxy
python advanced/http_proxy_client.py http://localhost:3128 http://www.example.com

# Through HTTPS proxy to HTTPS target
python advanced/http_proxy_client.py https://proxy.example.com:443 https://api.github.com

# With authentication (edit code to add auth headers)
# See proxy_handler() in the script for header customization
```

**C Tutorial Reference**: `thirdparty/mongoose/tutorials/http/http-proxy-client/main.c`

---

### 17. Multi-threaded Server (`advanced/multithreaded_server.py`)

Multi-threaded HTTP server demonstrating background work offloading with wakeup mechanism.

**Features**:

- Background work offloading to worker threads
- Fast path (single-threaded, immediate response) vs slow path (multi-threaded with delay)
- Thread-safe communication using Manager.wakeup()
- Connection ID pattern (pass conn.id to threads, not Connection object)
- Concurrent request processing demonstration
- **CRITICAL**: Requires `enable_wakeup=True` when creating Manager
- **CRITICAL**: Wakeup data must be bytes, not strings

**Usage**:

```bash
# Start multi-threaded server (2 second worker delay)
python advanced/multithreaded_server.py

# Custom port and sleep time
python advanced/multithreaded_server.py --listen http://0.0.0.0:8080 --sleep-time 5

# Test endpoints
curl http://localhost:8000/            # Homepage
curl http://localhost:8000/fast        # Immediate response
curl http://localhost:8000/slow        # 2-second delay (threaded)

# Test concurrency (all finish in ~2s instead of 6s)
curl http://localhost:8000/slow &
curl http://localhost:8000/slow &
curl http://localhost:8000/slow &
wait
```

**C Tutorial Reference**: `thirdparty/mongoose/tutorials/core/multi-threaded/main.c`

---

## Running the Examples

### Prerequisites

```bash
# Install cymongoose in development mode
cd /path/to/cymongoose
uv sync

# Or with pip
pip install -e .
```

### Optional: WebSocket Client Library

For testing WebSocket clients from Python:

```bash
uv add --dev websocket-client
# or
pip install websocket-client
```

### Running Examples

All examples are standalone Python scripts that can be run directly:

```bash
# From the examples directory
cd tests/examples

# Core HTTP/WebSocket
python http/http_server.py
python http/http_client.py https://httpbin.org/get
python websocket/websocket_server.py
python websocket/websocket_broadcast.py

# MQTT
python mqtt/mqtt_client.py mqtt://broker.hivemq.com:1883
python mqtt/mqtt_server.py

# Specialized HTTP
python http/http_streaming_client.py https://httpbin.org/stream/10
python http/http_file_upload.py
python http/http_restful_server.py
python http/http_sse_server.py

# Network Protocols
python network/sntp_client.py
python network/dns_client.py google.com
python network/tcp_echo_server.py
python network/udp_echo_server.py

# Advanced Features
python advanced/tls_https_server.py --skip-verify
python advanced/http_proxy_client.py http://localhost:3128 http://www.example.com
python advanced/multithreaded_server.py
```

---

## Example Structure

Each example follows this pattern:

1. **Imports**: Standard library + cymongoose imports
2. **Event Handler**: Main event processing function
3. **Helper Functions**: Protocol-specific logic
4. **Main Function**: Argument parsing and setup
5. **Run Loop**: Event loop with `Manager.poll()`

This mirrors the structure of Mongoose C tutorials for easier comparison.

---

## Common Patterns

### Event Loop Pattern

```python
manager = Manager(handler)
manager.listen("http://0.0.0.0:8000", http=True)

try:
    while True:
        manager.poll(1000)  # Poll every 1000ms
except KeyboardInterrupt:
    print("Shutting down...")
finally:
    manager.close()
```

### HTTP Handler Pattern

```python
def handler(conn, event, data):
    if event == MG_EV_HTTP_MSG:
        uri = data.uri
        method = data.method

        if uri == "/api/endpoint":
            conn.reply(200, "Response")
        else:
            conn.serve_dir(data, root_dir="./public")
```

### WebSocket Handler Pattern

```python
def handler(conn, event, data):
    if event == MG_EV_HTTP_MSG and data.uri == "/ws":
        conn.ws_upgrade(data)  # Upgrade to WebSocket

    elif event == MG_EV_WS_MSG:
        conn.ws_send(data.text)  # Echo message
```

### Timer Pattern

```python
def timer_callback():
    print("Timer fired!")

timer = manager.timer_add(1000, timer_callback, repeat=True)
```

---

## Validation Benefits

These examples serve multiple purposes:

- **API Coverage**: Validates all wrapped functions work in real scenarios (210 tests, 100% passing)
- **Documentation**: Provides copy-paste examples for users
- **Testing**: Acts as integration tests for complex workflows
- **Debugging**: Exposes edge cases and API usability issues (e.g., `enable_wakeup=True`, bytes vs strings)
- **Tutorial**: Helps C developers transition to Python wrapper
- **Learning**: Demonstrates production-ready patterns (signal handlers, graceful shutdown, drain())

---

## Example Summary

 **ALL 17 EXAMPLES COMPLETE**

| # | Category | Examples | Status |
|----------|----------|----------|--------|
| 1 | Core HTTP/WebSocket | 4 | [x] Complete |
| 2 | MQTT | 2 | [x] Complete |
| 3 | Specialized HTTP | 4 | [x] Complete |
| 4 | Network Protocols | 4 | [x] Complete |
| 5 | Advanced Features | 3 | [x] Complete |
| **Total** | | **17** | **[x] 100%** |

**Test Coverage**: 42 example tests covering all 17 examples (210 total tests passing)

---

## Contributing

All planned examples have been implemented!

If you'd like to contribute additional examples or improvements:

1. Follow the existing structure and naming conventions
2. Include comprehensive docstrings with C tutorial reference
3. Add command-line argument parsing for flexibility
4. Use production-ready patterns:
   - Signal handlers for graceful shutdown (`signal.signal(signal.SIGINT, signal_handler)`)
   - `conn.drain()` for graceful connection close
   - `poll(100)` for responsive shutdown
5. Include both programmatic and browser-based testing methods where applicable
6. Add comprehensive tests in `tests/examples/test_*.py`
7. Update this README with the new example
8. Ensure all tests pass (`make test`)

---

## License

MIT (same as cymongoose)
