# WSGI Framework Support

cymongoose can serve as the HTTP engine for standard Python web
frameworks. Instead of writing raw event handlers, you can run your
existing Flask, Django, Bottle, or Falcon application on cymongoose's
C event loop and get a significant performance boost with no code changes.

## WSGI Server

The `cymongoose.wsgi` module implements a PEP 3333 WSGI server. Any
WSGI-compatible application works out of the box.

### Quick Start

```python
from cymongoose.wsgi import serve

# Flask
from myapp import app
serve(app, "http://127.0.0.1:8000")

# Django
from django.core.wsgi import get_wsgi_application
serve(get_wsgi_application(), "http://127.0.0.1:8000")

# Bottle
from myapp import app
serve(app, "http://127.0.0.1:8000")
```

### Flask Example

```python
from flask import Flask, request, jsonify
from cymongoose.wsgi import serve

app = Flask(__name__)

@app.route("/")
def index():
    return "Hello from Flask on cymongoose!"

@app.route("/api/echo", methods=["POST"])
def echo():
    return jsonify(request.json)

@app.route("/api/greet/<name>")
def greet(name):
    return jsonify({"greeting": f"Hello, {name}!"})

if __name__ == "__main__":
    serve(app, "http://127.0.0.1:8000", workers=8)
```

### WSGIServer Class

For more control, use `WSGIServer` directly:

```python
from cymongoose.wsgi import WSGIServer

server = WSGIServer(app, workers=8)
conn = server.listen("http://127.0.0.1:8000")
print(f"Listening on port {conn.local_addr[1]}")
server.run()
```

**Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `app` | callable | (required) | PEP 3333 WSGI application |
| `workers` | int | 4 | Thread pool size for concurrent requests |
| `error_handler` | callable | None | Called on event loop errors (not app errors) |
| `stream_timeout` | float | 5.0 | Seconds a streaming worker waits on a full queue before aborting (prevents deadlock on client disconnect) |

**Methods:**

| Method | Description |
|--------|-------------|
| `listen(url)` | Start listening. Returns the listener `Connection`. |
| `run(poll_ms=100)` | Blocking event loop with SIGINT/SIGTERM handling. |
| `close()` | Shut down the server and release resources. |
| `manager` | Property: the underlying `Manager` instance. |

### Architecture

The WSGI adapter bridges cymongoose's non-blocking event loop with
WSGI's synchronous, blocking model:

1. HTTP request arrives via `MG_EV_HTTP_MSG`.
2. A WSGI `environ` dict is built from the `HttpMessage`.
3. The WSGI callable is submitted to a `ThreadPoolExecutor`.
4. The worker thread calls the application, collects the response
   (status, headers, body iterator).
5. The worker serialises the result and calls `Manager.wakeup()` to
   hand it back to the event loop.
6. On `MG_EV_WAKEUP` the handler sends the HTTP response via
   `conn.reply()`.

This keeps the event loop non-blocking while WSGI applications are free
to block in their handlers (database queries, file I/O, etc.).

### Threading Model

Each incoming request is dispatched to a thread from the pool.
The `workers` parameter controls concurrency:

- **CPU-bound apps**: set `workers` close to your core count.
- **I/O-bound apps** (database, external APIs): set `workers` higher
  (16-32) since threads will mostly be waiting.
- The event loop thread itself never blocks -- it only does HTTP
  parsing and response sending.

```python
# High concurrency for I/O-bound Flask app
server = WSGIServer(app, workers=32)
```

### Error Handling

Application exceptions are caught and returned as `500 Internal Server
Error` responses. The traceback is written to `sys.stderr`. The server
continues running -- a single failing request does not crash the event
loop.

```python
# Optional: handle event loop errors (not app errors)
def on_error(exc):
    logging.error("Event loop error: %s", exc)

server = WSGIServer(app, workers=4, error_handler=on_error)
```

### File Serving with `wsgi.file_wrapper`

The adapter provides `wsgi.file_wrapper` in the environ, implementing
the optional PEP 3333 protocol for file serving. WSGI applications
can use it to serve files efficiently:

```python
def file_app(environ, start_response):
    wrapper = environ["wsgi.file_wrapper"]
    fh = open("/path/to/file.bin", "rb")
    start_response("200 OK", [
        ("Content-Type", "application/octet-stream"),
    ])
    return wrapper(fh, blksize=8192)
```

The wrapper reads the file in blocks and iterates through the standard
WSGI response path. The underlying file handle is closed automatically
when iteration completes.

### Large Response Handling

`Manager.wakeup()` transmits data over a socketpair with a non-blocking
`send()`. The effective socket buffer is small (~9 KB on macOS, ~64 KB
on Linux), so the adapter **cannot send most responses inline**.

Responses exceeding 8 KB are automatically stashed in a thread-safe
dict keyed by UUID. Only the short key (~33 bytes) goes through
`wakeup()`, and the event loop thread retrieves the full response from
the dict. This is transparent to WSGI applications -- no special
handling is needed.

For applications that serve very large responses (file downloads,
large JSON payloads), be aware that the full response body is buffered
in memory before sending.

### Chunked Streaming

Responses under 1 MB are collected in memory and sent as a single
buffered reply (fast path). When the accumulated body exceeds 1 MB
during iteration, the adapter automatically switches to **chunked
transfer encoding**: it sends the HTTP headers immediately, then
streams each body chunk as it is yielded by the WSGI iterator.

This means:

- **Small API responses** (JSON, HTML): sent as a single reply with
  ``Content-Length`` -- no overhead.
- **Large file downloads**: streamed in chunks -- constant memory
  regardless of file size.
- **Lazy generators**: chunks are sent as they are produced, reducing
  time-to-first-byte for long-running responses.

Small chunks from fast generators are batched up to 256 KB before
sending to avoid flooding the wakeup pipe.

## See Also

- [ASGI Support](asgi.md) -- async framework adapter (FastAPI, Starlette, Quart)
- [WSGI Internals](../dev/wsgi.md) -- wakeup types, streaming design, thread safety
- [HTTP/HTTPS Guide](http.md) -- raw event handler approach
- [Threading Guide](../advanced/threading.md) -- thread-safety details
- [Performance Tuning](../advanced/performance.md) -- benchmarking tips
- [Examples](../examples.md) -- micro-framework and other examples
