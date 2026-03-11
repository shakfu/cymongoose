# User Guide

This guide covers protocol-specific usage patterns and best practices for cymongoose.

## Overview

cymongoose is organized around an event-driven architecture. Your application creates a `Manager`, registers event handlers, and runs the event loop.

## Basic Pattern

All cymongoose applications follow this pattern:

```python
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
```

## Event Handler

The event handler receives three arguments:

```python
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
```

### Common Events

| Event | When Fired | Data Type |
|---|---|---|
| `MG_EV_ERROR` | Error occurred | `str` |
| `MG_EV_OPEN` | Connection opened | `None` |
| `MG_EV_ACCEPT` | Incoming connection | `None` |
| `MG_EV_CONNECT` | Outbound connection established | `None` |
| `MG_EV_CLOSE` | Connection closing | `None` |
| `MG_EV_READ` | Data available | `None` |
| `MG_EV_WRITE` | Ready to write | `None` |

## Best Practices

### Signal Handling

Use signal handlers instead of try/except for Ctrl+C:

```python
shutdown_requested = False

def signal_handler(sig, frame):
    global shutdown_requested
    shutdown_requested = True

signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)
```

**Why?** The event loop releases the GIL for performance, which delays `KeyboardInterrupt` handling.

### Graceful Shutdown

Use `conn.drain()` instead of `conn.close()`:

```python
def handler(conn, ev, data):
    if ev == MG_EV_HTTP_MSG:
        conn.reply(200, b"Goodbye!")
        conn.drain()  # Flushes send buffer before closing
```

### Poll Timeout

Use `poll(100)` for responsive shutdown with low CPU:

```python
while not shutdown_requested:
    manager.poll(100)  # 100ms - responsive and efficient
```

### Error Handling

Handle errors in the event callback:

```python
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
```

## Per-Protocol Guides

See the protocol-specific guides for detailed information:

- [HTTP/HTTPS](http.md) - HTTP/HTTPS servers and clients
- [WebSocket](websocket.md) - WebSocket communication
- [MQTT](mqtt.md) - MQTT publish/subscribe
- [Network](network.md) - TCP/UDP, DNS, SNTP
- [TLS](tls.md) - TLS/SSL configuration

## Advanced Topics

For performance optimization, threading, and other advanced topics:

- [GIL-free Performance](../advanced/nogil.md) - GIL-free performance optimization
- [Threading](../advanced/threading.md) - Multi-threaded patterns
- [Performance](../advanced/performance.md) - Performance tuning
- [Shutdown](../advanced/shutdown.md) - Proper shutdown handling

## Next Steps

- Follow the [HTTP](http.md) guide for web servers
- See [WebSocket](websocket.md) for real-time communication
- Check [Examples](../examples.md) for complete examples
