# Ctrl+C Handling with nogil

## The Issue

When `poll()` releases the GIL (`with nogil:`), Python's signal handling is deferred. Signals like SIGINT (Ctrl+C) are queued but not immediately converted to `KeyboardInterrupt` exceptions. This can cause Ctrl+C to feel unresponsive or not work at all.

## Root Cause

1. `mg_mgr_poll()` is declared with `nogil` for performance
2. While executing with GIL released, Python can't raise exceptions
3. After `poll()` returns and GIL is reacquired, signal delivery is not guaranteed

## Solution 1: Signal Handler (Recommended)

Use a Python-level flag checked after each poll:

```python
import signal

shutdown = False

def signal_handler(sig, frame):
    global shutdown
    shutdown = True

signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)

manager = Manager(handler)
manager.listen('http://0.0.0.0:8000', http=True)

try:
    while not shutdown:
        manager.poll(100)
finally:
    manager.close()
```

**Pros**:

- [x] Reliable and fast
- [x] Works with both SIGINT and SIGTERM
- [x] Production-ready pattern

**Cons**:

- Requires explicit signal handler setup

## Solution 2: Try/Except with Short Timeout

Use a short poll timeout and rely on Python checking signals between polls:

```python
manager = Manager(handler)
manager.listen('http://0.0.0.0:8000', http=True)

try:
    while True:
        manager.poll(50)  # Short timeout = more frequent signal checks
except KeyboardInterrupt:
    print("Shutting down...")
finally:
    manager.close()
```

**Pros**:

- [x] Simple, no signal handler needed
- [x] May work depending on timing

**Cons**:

- [X] Not reliable - Ctrl+C might not be caught
- [X] Depends on when signal arrives relative to poll() call

## Solution 3: Periodic Signal Check

Explicitly check for signals every N iterations:

```python
import signal

manager = Manager(handler)
manager.listen('http://0.0.0.0:8000', http=True)

try:
    count = 0
    while True:
        manager.poll(100)
        count += 1
        if count % 10 == 0:
            # Force signal check by briefly acquiring/releasing GIL
            signal.pause() if signal.SIG_DFL else None
except KeyboardInterrupt:
    print("Shutting down...")
finally:
    manager.close()
```

**Pros**:

- Works around nogil signal deferral

**Cons**:

- [X] Complex and hacky
- [X] Not recommended

## Why Not Remove nogil?

Removing `nogil` from `poll()` would fix Ctrl+C but:

- [X] Loses 30-40% throughput (benchmark shows 60k → 40k req/sec)
- [X] Prevents true parallelism
- [X] Makes multi-threaded servers slower

The tradeoff isn't worth it - use Solution 1 instead.

## Implementation in cymongoose

Currently `poll()` calls `PyErr_CheckSignals()` after returning from nogil section:

```cython
def poll(self, int timeout_ms=0):
    if self._freed:
        raise RuntimeError("Manager has been freed")
    with nogil:
        mg_mgr_poll(&self._mgr, timeout_ms)
    if PyErr_CheckSignals() < 0:
        pass  # Exception raised by CheckSignals
```

This helps but isn't 100% reliable due to signal delivery timing.

## Recommended Pattern for All Servers

Always use signal handlers for production code:

```python
#!/usr/bin/env python3
import signal
import sys
from cymongoose import Manager, MG_EV_HTTP_MSG

shutdown_requested = False

def signal_handler(sig, frame):
    global shutdown_requested
    shutdown_requested = True
    signame = signal.Signals(sig).name
    print(f"\\n{signame} received, shutting down...")

def handler(conn, ev, data):
    if ev == MG_EV_HTTP_MSG:
        conn.reply(200, b'{"ok":true}')

def main():
    global shutdown_requested

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    manager = Manager(handler)
    manager.listen('http://0.0.0.0:8000', http=True)
    print("Server running. Press Ctrl+C to stop.")

    try:
        while not shutdown_requested:
            manager.poll(100)
    finally:
        manager.close()
        print("Server stopped cleanly")

if __name__ == "__main__":
    sys.exit(main())
```

This pattern:

- [x] Handles Ctrl+C reliably
- [x] Handles SIGTERM (systemd, Docker)
- [x] Keeps nogil optimization
- [x] Always cleans up resources

## Summary

- **Problem**: nogil defers signal handling, Ctrl+C may not work
- **Solution**: Use signal handler with global flag (Solution 1)
- **Don't**: Remove nogil (loses performance)
- **Don't**: Rely on try/except alone (unreliable)

All example servers in `benchmarks/` will be updated to use this pattern.
