# Connection Draining: Graceful Close

## Overview

When closing HTTP connections from the server side, there are two methods:

- **`conn.close()`**: Immediate close (may lose buffered data)
- **`conn.drain()`**: Graceful close (flushes data first) [x] **Recommended**

## The Problem

If you close a connection immediately after sending a response, the client may not receive the full data:

```python
# [X] BAD: May not send complete response
def handler(conn, ev, data):
    if ev == MG_EV_HTTP_MSG:
        conn.reply(200, b"Large response..." * 1000)
        conn.close()  # Closes immediately!
```

The issue: `close()` immediately tears down the connection, even if there's data in the send buffer.

## The Solution: drain()

Use `conn.drain()` to mark the connection for graceful shutdown:

```python
# [x] GOOD: Ensures response is fully sent
def handler(conn, ev, data):
    if ev == MG_EV_HTTP_MSG:
        conn.reply(200, b"Large response..." * 1000)
        conn.drain()  # Closes after send buffer empties
```

### What drain() Does

1. **Sets `conn.is_draining = 1`** - Marks connection for closure
2. **Stops reading** - No more data accepted from client
3. **Flushes send buffer** - Continues sending buffered data
4. **Closes when empty** - Connection closes after all data sent

This is the **Mongoose-recommended pattern** for server-initiated closes.

## API Reference

### conn.drain()

```python
def drain(self):
    """Mark connection for graceful closure.

    Sets is_draining=1, which tells Mongoose to:
    1. Stop reading from the socket
    2. Flush any buffered outgoing data
    3. Close the connection after send buffer is empty

    This is the recommended way to close connections from the server side.
    """
```

**When to use**:

- [x] After sending HTTP response
- [x] After sending last WebSocket message
- [x] When you want client to receive all data

### conn.close()

```python
def close(self):
    """Immediately close the connection.

    For graceful shutdown, use drain() instead.
    """
```

**When to use**:

- [!] Handling protocol violations
- [!] Malicious connections (timeout/abuse)
- [!] Emergency shutdown

**Avoid for normal responses** - use `drain()` instead.

### conn.is_draining (property)

```python
@property
def is_draining(self) -> bool:
    """Return True if connection is draining."""
```

**Read-only property** to check if connection is marked for drainage.

## Usage Patterns

### HTTP Server: One-shot Response

Most common pattern - send response and close:

```python
def handler(conn, ev, data):
    if ev == MG_EV_HTTP_MSG:
        conn.reply(200, b"Hello, World!")
        conn.drain()  # Close after response sent
```

### HTTP Server: Keep-Alive

Don't call `drain()` if you want connection reuse:

```python
def handler(conn, ev, data):
    if ev == MG_EV_HTTP_MSG:
        conn.reply(200, b"Hello, World!")
        # No drain() - connection stays open for next request
```

HTTP/1.1 keep-alive will automatically manage the connection.

### WebSocket: Graceful Disconnect

Send close frame, then drain:

```python
def handler(conn, ev, data):
    if ev == MG_EV_WS_MSG:
        if should_disconnect():
            conn.ws_send("Goodbye!", WEBSOCKET_OP_TEXT)
            conn.drain()  # Close after message sent
```

### Checking Drain State

Monitor connection state:

```python
def handler(conn, ev, data):
    if ev == MG_EV_POLL:
        if conn.is_draining:
            print("Connection is draining...")
```

## Examples

### Example 1: HTTP Server with Drain

```python
from cymongoose import Manager, MG_EV_HTTP_MSG

def handler(conn, ev, data):
    if ev == MG_EV_HTTP_MSG:
        # Log request
        print(f"{data.method} {data.uri}")

        # Send response
        conn.reply(
            200,
            b'{"status":"ok"}',
            headers={"Content-Type": "application/json"}
        )

        # Graceful close after response
        conn.drain()

manager = Manager(handler)
manager.listen('http://0.0.0.0:8000', http=True)

while True:
    manager.poll(100)
```

### Example 2: Conditional Drain

Close connection only for specific paths:

```python
def handler(conn, ev, data):
    if ev == MG_EV_HTTP_MSG:
        if data.uri == "/quit":
            conn.reply(200, b"Goodbye!")
            conn.drain()  # Close this connection
        else:
            conn.reply(200, b"Hello!")
            # Keep connection alive
```

### Example 3: Drain All Connections on Shutdown

Gracefully close all connections during server shutdown:

```python
shutdown_requested = False

def handler(conn, ev, data):
    if ev == MG_EV_HTTP_MSG:
        if shutdown_requested:
            conn.reply(503, b"Server shutting down")
            conn.drain()
        else:
            conn.reply(200, b"OK")

# ... shutdown logic sets shutdown_requested = True
```

## Common Mistakes

### [X] DON'T: Drain after every response (HTTP/1.1)

```python
# BAD: Prevents connection reuse
def handler(conn, ev, data):
    if ev == MG_EV_HTTP_MSG:
        conn.reply(200, b"OK")
        conn.drain()  # [X] Closes connection every time
```

This disables HTTP keep-alive and forces new connections for each request.

### [X] DON'T: Use close() for normal responses

```python
# BAD: May lose data
def handler(conn, ev, data):
    if ev == MG_EV_HTTP_MSG:
        conn.reply(200, large_response)
        conn.close()  # [X] Immediate close may truncate response
```

### [x] DO: Use drain() when closing from server

```python
# GOOD: Ensures complete data delivery
def handler(conn, ev, data):
    if ev == MG_EV_HTTP_MSG:
        conn.reply(200, large_response)
        conn.drain()  # [x] Graceful close
```

### [x] DO: Let HTTP keep-alive manage connections

```python
# GOOD: Connection reuse enabled
def handler(conn, ev, data):
    if ev == MG_EV_HTTP_MSG:
        conn.reply(200, b"OK")
        # No drain() - connection stays open
```

## Performance Considerations

### Drain vs Close Performance

- **`drain()`**: Adds ~1-10ms latency (time to flush buffers)
- **`close()`**: Instant, but may lose data

For most HTTP responses (< 10KB), the difference is negligible (< 1ms).

### Connection Reuse

HTTP/1.1 keep-alive reuses connections:

- **Without drain**: ~60,000 req/sec (benchmark result)
- **With drain every request**: ~45,000 req/sec (more TCP overhead)

**Best practice**: Only drain when actually closing the connection (e.g., WebSocket disconnect, server shutdown, or explicit "Connection: close" header).

## Under the Hood

What Mongoose does when `is_draining = 1`:

1. **`MG_EV_POLL` events continue** - Connection stays in event loop
2. **`mg_iobuf_del(&c->recv, c->recv.len)`** - Clear receive buffer
3. **`mg_send()` still works** - Can still send data
4. **When `c->send.len == 0`**: Calls `mg_close_conn()`

This ensures buffered data is flushed before closing.

## Summary

| Method | Use Case | Data Loss Risk | Latency |
|--------|----------|----------------|---------|
| `conn.drain()` | [x] Normal server-initiated close | None | +1-10ms |
| `conn.close()` | [!] Emergency/protocol violation | Possible | Instant |
| *(no call)* | [x] HTTP keep-alive | N/A | N/A |

**Default recommendation**: Use `drain()` when you need to close a connection after sending data. Otherwise, let HTTP keep-alive manage connections automatically.

---

See also:

- `cleanup_and_shutdown.md` - Manager cleanup
- `shutdown_best_practices.md` - Graceful server shutdown
