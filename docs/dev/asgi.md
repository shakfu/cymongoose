# ASGI Adapter: Design Analysis

This document captures the complexity analysis and design considerations
for a future ASGI server adapter. For the user-facing placeholder see
[ASGI Framework Support](../guide/asgi.md).

## WSGI vs ASGI Complexity

WSGI is request-response: one function call, one return value. The
adapter's complexity comes from bridging threads, not from the protocol.

```python
# The entire WSGI contract
def app(environ, start_response):
    start_response("200 OK", headers)
    return [body]
```

ASGI is a bidirectional async protocol with three sub-protocols, each
with its own state machine:

```python
# HTTP: 3 message types, ordered lifecycle
async def app(scope, receive, send):
    # scope = {"type": "http", "method": "GET", "path": "/", ...}
    request = await receive()  # {"type": "http.request", "body": b"..."}
    await send({"type": "http.response.start", "status": 200, "headers": [...]})
    await send({"type": "http.response.body", "body": b"..."})

# WebSocket: 6+ message types, stateful connection
async def app(scope, receive, send):
    # scope = {"type": "websocket", ...}
    msg = await receive()  # {"type": "websocket.connect"}
    await send({"type": "websocket.accept"})
    while True:
        msg = await receive()  # {"type": "websocket.receive", "text": "..."}
        await send({"type": "websocket.send", "text": "echo"})
        # also: websocket.disconnect, websocket.close

# Lifespan: startup/shutdown hooks
async def app(scope, receive, send):
    # scope = {"type": "lifespan"}
    msg = await receive()  # {"type": "lifespan.startup"}
    await send({"type": "lifespan.startup.complete"})
    msg = await receive()  # {"type": "lifespan.shutdown"}
    await send({"type": "lifespan.shutdown.complete"})
```

## Comparison

| Aspect | WSGI | ASGI |
|---|---|---|
| Concurrency model | Thread pool (implemented) | asyncio event loop -- need to bridge two event loops (mongoose + asyncio) |
| Sub-protocols | 1 (HTTP) | 3 (HTTP, WebSocket, Lifespan) |
| Message types | 1 in, 1 out | ~12 across sub-protocols |
| Connection lifecycle | Stateless | Stateful (especially WebSocket) |
| Streaming | Iterator (implemented) | Async generator via `receive()`/`send()` callbacks |
| Request body | Available upfront in environ | May arrive in multiple `http.request` messages |
| Response | Single `start_response` + body | Separate `response.start` and `response.body` messages |

## The Hard Part: Bridging Two Event Loops

The core challenge is not any single message type -- it is bridging two
event loops. cymongoose's `AsyncManager` runs mongoose's poll loop in a
background thread while exposing an asyncio-friendly interface. The ASGI
adapter would need to:

1. Receive HTTP/WS events from mongoose (C thread via `MG_EV_*`).
2. Feed them into per-connection asyncio queues as ASGI `receive()`
   messages.
3. Accept ASGI `send()` messages from the application coroutine.
4. Route them back to mongoose via `wakeup()` or direct `conn.*` calls.

The WSGI adapter already solved a simpler version of this problem (thread
pool + wakeup for responses). The ASGI version requires the same
pattern but in both directions, with per-connection state tracking.

## Sub-Protocol Notes

### HTTP

Most similar to the WSGI adapter. Key differences:

- Request body may arrive incrementally (`http.request` with
  `more_body=True`). The WSGI adapter buffers the full body upfront
  from `HttpMessage.body_bytes`; for ASGI, this is still acceptable
  since mongoose delivers the complete message on `MG_EV_HTTP_MSG`.
- Response is two messages (`response.start` + `response.body`) instead
  of one. The adapter would buffer `response.start` and send the full
  response on `response.body`, or start chunked encoding if
  `more_body=True`.

### WebSocket

The most natural mapping. cymongoose already has:

- `conn.ws_upgrade()` -> `websocket.accept`
- `MG_EV_WS_MSG` -> `websocket.receive`
- `conn.ws_send()` -> `websocket.send`
- `MG_EV_CLOSE` -> `websocket.disconnect`

The main work is wiring these into per-connection asyncio queues and
managing the connection state machine (connecting -> open -> closing ->
closed).

### Lifespan

Simplest sub-protocol (~30 lines). Fires startup/shutdown events when
the server starts and stops. Maps to `AsyncManager.__aenter__` and
`__aexit__`.

## Estimated Scope

- WSGI adapter: ~350 lines of code, ~35 tests.
- ASGI adapter (estimated): ~600-800 lines, ~50-70 tests.
- Bulk of the work: HTTP and WebSocket state machines, asyncio bridge.
- Lifespan: ~30 lines.

## Prerequisites

Before implementing, the WSGI adapter should be validated in real-world
use to confirm the wakeup transport, stash mechanism, and streaming
design are solid. The ASGI adapter will reuse these patterns.

## See Also

- [ASGI Framework Support](../guide/asgi.md) -- user-facing placeholder
- [WSGI Internals](wsgi.md) -- existing adapter architecture
- [AsyncManager API](../api/async_manager.md) -- asyncio integration
