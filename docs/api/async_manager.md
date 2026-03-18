# AsyncManager Class

::: cymongoose.AsyncManager
    options:
      members: true
      undoc-members: true
      special-members:
        - __init__
      member-order: bysource

## Overview

`AsyncManager` wraps `Manager` for use with Python's `asyncio`. It runs the
mongoose event loop in a daemon thread while the asyncio event loop runs
concurrently. Since `poll()` releases the GIL, both loops make progress
without blocking each other.

## Basic Usage

```python
import asyncio
from cymongoose import AsyncManager, MG_EV_HTTP_MSG

def handler(conn, ev, data):
    if ev == MG_EV_HTTP_MSG:
        conn.reply(200, b"Hello from async!")

async def main():
    async with AsyncManager(handler) as am:
        am.listen("http://0.0.0.0:8080")
        # Server is running -- do async work here
        await asyncio.sleep(60)

asyncio.run(main())
```

## Constructor

::: cymongoose.AsyncManager.__init__
    options:
      members: true

### Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `handler` | `Callable` or `None` | `None` | Default event handler `(conn, ev, data) -> None` |
| `poll_interval` | `int` | `100` | Milliseconds between `poll()` calls |
| `error_handler` | `Callable` or `None` | `None` | Called with `(exc: Exception)` when a handler raises |
| `shutdown_timeout` | `float` | `30` | Seconds to wait for the poll thread on exit |

## Listening for Connections

```python
async with AsyncManager(handler) as am:
    # HTTP server
    am.listen("http://0.0.0.0:8080")

    # With per-listener handler
    am.listen("http://0.0.0.0:9090", handler=api_handler)

    # MQTT broker
    am.mqtt_listen("mqtt://0.0.0.0:1883")
```

### Methods

::: cymongoose.AsyncManager.listen
    options:
      members: true

::: cymongoose.AsyncManager.mqtt_listen
    options:
      members: true

## Making Connections

```python
async with AsyncManager(handler) as am:
    # HTTP client
    am.connect("http://example.com:80", handler=client_handler)

    # MQTT client
    am.mqtt_connect("mqtt://broker.com:1883", clean_session=True)

    # SNTP client
    am.sntp_connect("udp://time.google.com:123", handler=time_handler)
```

### Methods

::: cymongoose.AsyncManager.connect
    options:
      members: true

::: cymongoose.AsyncManager.mqtt_connect
    options:
      members: true

::: cymongoose.AsyncManager.sntp_connect
    options:
      members: true

## Timers

```python
async with AsyncManager() as am:
    # One-shot timer
    am.timer_add(5000, lambda: print("fired"))

    # Repeating timer
    timer = am.timer_add(1000, heartbeat, repeat=True)
    # ...
    timer.cancel()
```

::: cymongoose.AsyncManager.timer_add
    options:
      members: true

## Thread-Safe Communication

### Wakeup

`wakeup()` is thread-safe and does not require the internal lock:

```python
async with AsyncManager(handler, enable_wakeup=True) as am:
    listener = am.listen("http://0.0.0.0:8080")
    # From any thread or coroutine:
    am.wakeup(conn_id, b"data")
```

::: cymongoose.AsyncManager.wakeup
    options:
      members: true

### Scheduling Asyncio Work from Handlers

Use `schedule()` to push work from the mongoose poll thread back onto
the asyncio event loop:

```python
async def process_request(data):
    result = await some_async_operation(data)
    print(f"Processed: {result}")

def handler(conn, ev, data):
    if ev == MG_EV_HTTP_MSG:
        conn.reply(200, b"Accepted")
        # Schedule async work from the handler (runs on poll thread)
        am.schedule(process_request(data.body_text))

async with AsyncManager(handler) as am:
    am.listen("http://0.0.0.0:8080")
    await asyncio.sleep(3600)
```

::: cymongoose.AsyncManager.schedule
    options:
      members: true

## Properties

::: cymongoose.AsyncManager.manager
    options:
      members: true

::: cymongoose.AsyncManager.running
    options:
      members: true

## Shutdown Behavior

When the `async with` block exits, `__aexit__` shuts down the poll thread:

1. Signals the thread to stop and sends a wakeup.
2. Waits 5 seconds for the thread to join.
3. If still alive: emits a `RuntimeWarning`, retries the wakeup, waits
   another 5 seconds.
4. Repeats step 3 until `shutdown_timeout` is reached.
5. At the hard limit: emits a final warning and moves on without calling
   `Manager.close()`.

```python
# Tune the timeout for your application
async with AsyncManager(handler, shutdown_timeout=10) as am:
    am.listen("http://0.0.0.0:8080")
    # ...
# __aexit__ handles shutdown automatically
```

If the poll thread exits cleanly, `Manager.close()` is called and all
resources are freed. If the thread is abandoned (handler blocked beyond
the timeout), the daemon thread dies at process exit.

See [Graceful Shutdown](../advanced/shutdown.md) for more patterns.

## Differences from Manager

| Feature | `Manager` | `AsyncManager` |
|---------|-----------|-----------------|
| Event loop | Manual `poll()` calls | Automatic in daemon thread |
| Concurrency | Single-threaded or manual threading | Runs alongside asyncio |
| Shutdown | Explicit `close()` | Automatic via `__aexit__` |
| Thread safety | `poll()` not reentrant | Serialised by internal `RLock` |
| Wakeup | Opt-in via `enable_wakeup=True` | Always enabled |

## See Also

- [Manager](manager.md) -- the underlying synchronous API
- [Threading](../advanced/threading.md) -- thread-safety model
- [Graceful Shutdown](../advanced/shutdown.md) -- shutdown patterns
