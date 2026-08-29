# GIL-Free Performance Optimization

cymongoose achieves C-level performance through the `nogil` optimization.

## Overview

The **nogil** (no-GIL) optimization allows 24 performance-critical methods to release Python's Global Interpreter Lock (GIL) during execution, enabling true parallel execution and minimizing Python overhead.

**Performance Impact**: Achieves 60k+ req/sec (6-37x faster than pure Python frameworks)

## How It Works

All critical C API calls unconditionally release the GIL (since v0.2.0):

```python
# Critical operations release the GIL
manager.poll(100)  # Releases GIL - other threads can execute

# Network operations release GIL
conn.send(data)    # Releases GIL during C call
conn.reply(...)    # Releases GIL during C call
```

## Methods with nogil

The following 24 methods release the GIL for parallel execution:

**Network Operations:**

- `send()`

- `close()`

- `resolve()`

- `resolve_cancel()`

**WebSocket:**

- `ws_send()`

- `ws_upgrade()`

**MQTT:**

- `mqtt_pub()`

- `mqtt_sub()`

- `mqtt_unsub()`

- `mqtt_ping()`

- `mqtt_pong()`

- `mqtt_disconnect()`

**HTTP:**

- `reply()`

- `serve_dir()`

- `serve_file()`

- `http_chunk()`

- `http_sse()`

**TLS:**

- `tls_init()`

- `tls_free()`

**Utilities:**

- `sntp_request()`

- `http_basic_auth()`

- `error()`

**Manager:**

- `poll()`

- `wakeup()` (thread-safe)

## Always Enabled

nogil is **unconditional** — there is no compile-time or runtime switch to disable it. Every build releases the GIL on the methods listed above. Prior versions (before v0.2.0) supported a `USE_NOGIL` compile flag; that path was removed because it was always enabled in practice.

### Rebuild After Code Changes

```bash
make build          # Rebuild the Cython extension
# or
uv sync --reinstall-package cymongoose
```

## Performance Comparison

Benchmark results (Apple Silicon, `wrk -t4 -c100 -d10s`):

| Configuration | Req/sec | Performance |
|---|---|---|
| cymongoose (nogil) | 88,710 | 100% (baseline) |
| Pure Python (aiohttp) | 42,452 | ~48% |

Historical note: early builds with nogil accidentally disabled achieved ~35k req/sec (~40% of baseline). That misconfiguration is no longer possible.

## Thread Safety

### Mongoose TLS Compatibility

nogil works safely with Mongoose's built-in TLS because:

1. TLS operations are event-loop based (no background threads)

2. No internal locks in Mongoose TLS implementation

3. All TLS state is per-connection (no shared state)

```python
# Safe: TLS + nogil
def handler(conn, ev, data):
    if ev == MG_EV_ACCEPT:
        opts = TlsOpts(cert=cert, key=key)
        conn.tls_init(opts)  # Releases GIL safely
```

### Signal Handling

With nogil, `KeyboardInterrupt` may be delayed during `poll()`:

```python
# DON'T rely on try/except for Ctrl+C
try:
    while True:
        manager.poll(100)  # GIL released - signals deferred
except KeyboardInterrupt:
    pass  # May not catch reliably

# DO use signal handlers
shutdown_requested = False

def signal_handler(sig, frame):
    global shutdown_requested
    shutdown_requested = True

signal.signal(signal.SIGINT, signal_handler)

while not shutdown_requested:
    manager.poll(100)
```

### Memory Lifetime

Python objects remain valid during nogil C calls:

```python
# Safe: bytes object stays alive
data = b"Hello"
conn.send(data)  # Pointer to data.buf is valid during nogil
```

## Implementation Details

### Cython Code

```cython
# Unconditional nogil on every C API call
with nogil:
    result = mg_send(conn, buf, length)
```

All Mongoose C functions must be declared with `nogil` in `mongoose.pxd`:

```cython
cdef extern from "mongoose.h":
    bint mg_send(mg_connection *conn, const void *buf, size_t len) nogil
```

## Best Practices

1. **Use signal handlers** for Ctrl+C, not try/except

2. **Don't access Python objects** from background threads without GIL

3. **Use `AsyncManager` or `Manager.wakeup()`** for cross-thread communication

4. **Benchmark** against pure-Python frameworks to validate performance gains

## Troubleshooting

### Performance Lower Than Expected

1. Check poll timeout (use 100ms, not 5000ms)

2. Profile handler code — Python business logic dominates real workloads

3. Ensure TLS is only used when needed

4. Run benchmarks (`make bench-quick`) to establish a baseline

## See Also

- [Performance tuning guide](performance.md)

- [Multi-threading patterns](threading.md)

- [Signal handling best practices](shutdown.md)
