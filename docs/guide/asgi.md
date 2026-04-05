# ASGI Framework Support

cymongoose can serve ASGI applications (FastAPI, Starlette, Django
async, Quart) on its C event loop, providing HTTP and WebSocket
support.

## Quick Start

```python
from cymongoose.asgi import serve

# FastAPI
from myapp import app
serve(app, "http://127.0.0.1:8000")

# Starlette
from myapp import app
serve(app, "http://127.0.0.1:8000")
```

### FastAPI Example

```python
from fastapi import FastAPI
from cymongoose.asgi import serve

app = FastAPI()

@app.get("/")
async def index():
    return {"message": "Hello from FastAPI on cymongoose!"}

@app.get("/items/{item_id}")
async def get_item(item_id: int, q: str = ""):
    return {"item_id": item_id, "q": q}

if __name__ == "__main__":
    serve(app, "http://127.0.0.1:8000")
```

### Starlette WebSocket Example

```python
from starlette.applications import Starlette
from starlette.responses import PlainTextResponse
from starlette.routing import Route, WebSocketRoute
from starlette.websockets import WebSocket
from cymongoose.asgi import serve

async def homepage(request):
    return PlainTextResponse("Hello!")

async def ws_endpoint(websocket: WebSocket):
    await websocket.accept()
    while True:
        data = await websocket.receive_text()
        await websocket.send_text(f"Echo: {data}")

app = Starlette(routes=[
    Route("/", homepage),
    WebSocketRoute("/ws", ws_endpoint),
])

if __name__ == "__main__":
    serve(app, "http://127.0.0.1:8000")
```

## ASGIServer Class

For more control, use `ASGIServer` directly:

```python
import asyncio
from cymongoose.asgi import ASGIServer

async def main():
    server = ASGIServer(app)
    conn = await server.start("http://127.0.0.1:8000")
    print(f"Listening on port {conn.local_addr[1]}")
    try:
        await asyncio.Event().wait()  # Run until interrupted
    finally:
        await server.stop()

asyncio.run(main())
```

**Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `app` | callable | (required) | ASGI 3.0 application |
| `error_handler` | callable | None | Called on event-loop-level errors (not app errors) |

**Methods:**

| Method | Description |
|--------|-------------|
| `start(url)` | Start listening. Returns the listener `Connection`. Must be awaited. |
| `stop()` | Stop the server, cancel ASGI tasks, release resources. Must be awaited. |
| `manager` | Property: the underlying `Manager` instance. |

## Architecture

The ASGI adapter bridges cymongoose's C event loop (running in a
background thread) with Python's asyncio event loop:

1. HTTP/WebSocket events arrive via `MG_EV_HTTP_MSG`, `MG_EV_WS_MSG`,
   etc. in the mongoose poll thread.
2. Events are converted to ASGI `receive` messages and pushed into
   per-connection `asyncio.Queue` instances via
   `loop.call_soon_threadsafe`.
3. The ASGI application coroutine awaits `receive()` and calls
   `send()` on the asyncio thread.
4. `send()` serialises the response and routes it back to the
   mongoose thread via `Manager.wakeup()` (using the stash for
   payloads > 8 KB).

### WebSocket Upgrade

WebSocket upgrades are completed eagerly in the `MG_EV_HTTP_MSG`
handler by calling `conn.ws_upgrade()` immediately.  This is
necessary because cymongoose's `HttpMessage` views are invalidated
after the event handler returns.  The ASGI application's
`websocket.accept` message is acknowledged but does not trigger
any additional action on the mongoose side.

## Supported Sub-Protocols

### HTTP

Full request/response cycle:

- `http.request` -- delivered with the complete request body
  (mongoose buffers the full body before firing `MG_EV_HTTP_MSG`)
- `http.response.start` -- buffered until `http.response.body` arrives
- `http.response.body` -- triggers the actual HTTP response.  Supports
  `more_body=True` for chunked streaming (see below)
- `http.disconnect` -- delivered on `MG_EV_CLOSE`

### WebSocket

Full bidirectional messaging:

- `websocket.connect` -- delivered after the upgrade request
- `websocket.accept` -- acknowledged (upgrade already completed)
- `websocket.receive` -- text or binary frames from the client
- `websocket.send` -- text or binary frames to the client
- `websocket.close` -- closes the connection
- `websocket.disconnect` -- delivered on `MG_EV_CLOSE`

### Lifespan

The server implements the ASGI lifespan sub-protocol for applications
that need startup/shutdown hooks (e.g. initialising a database pool):

- `lifespan.startup` -- sent before the listener binds
- `lifespan.startup.complete` -- unblocks `start()` and begins
  accepting connections
- `lifespan.startup.failed` -- propagated as `RuntimeError` from
  `start()`
- `lifespan.shutdown` -- sent during `stop()` after all connections
  are closed
- `lifespan.shutdown.complete` -- unblocks `stop()`

Applications that don't handle the lifespan scope (raise an exception
or return without sending a message) are detected automatically and
the server proceeds normally.

```python
from starlette.applications import Starlette

app = Starlette(
    on_startup=[lambda: print("Starting up...")],
    on_shutdown=[lambda: print("Shutting down...")],
)
```

### Streaming HTTP Responses

Applications can send responses incrementally using chunked transfer
encoding by setting `more_body=True` on `http.response.body`:

```python
async def streaming_app(scope, receive, send):
    await receive()
    await send({
        "type": "http.response.start",
        "status": 200,
        "headers": [[b"content-type", b"text/plain"]],
    })

    for chunk in generate_data():
        await send({
            "type": "http.response.body",
            "body": chunk,
            "more_body": True,
        })

    # Final message: more_body=False (or omitted) ends the stream.
    await send({"type": "http.response.body", "body": b"", "more_body": False})
```

The first `http.response.body` with `more_body=True` triggers chunked
transfer encoding.  Subsequent body messages send individual HTTP
chunks.  A final message with `more_body=False` (or omitted) sends the
terminating empty chunk.

Responses without `more_body=True` use the original buffered path
(single `Content-Length` response).

**Backpressure:** An `asyncio.Semaphore` (capacity 16) limits in-flight
wakeups per streaming connection.  If the application sends chunks
faster than the poll thread can drain them, `await send()` blocks
until a permit is released, preventing socketpair buffer exhaustion.

## Error Handling

Application exceptions are caught per-connection.  If an HTTP
application raises before sending a response, a 500 Internal Server
Error is returned automatically.  The traceback is printed to stderr.

```python
server = ASGIServer(app, error_handler=lambda exc: print(f"Error: {exc}"))
```

## ASGI vs WSGI

| | WSGI | ASGI |
|---|---|---|
| Frameworks | Flask, Django, Bottle | FastAPI, Starlette, Django async |
| Concurrency | Thread pool | asyncio coroutines |
| WebSocket | Not supported | Supported |
| Streaming | Chunked (> 1 MB auto) | Chunked (via `more_body`) |
| Lifespan | N/A | Supported |
| Import | `from cymongoose.wsgi import serve` | `from cymongoose.asgi import serve` |

## See Also

- [WSGI Support](wsgi.md) -- synchronous framework adapter
- [HTTP/HTTPS Guide](http.md) -- raw event handler approach
- [AsyncManager API](../api/async_manager.md) -- asyncio integration
- [ASGI Internals](../dev/asgi.md) -- wakeup types, thread safety, design decisions
