# Cleanup and Shutdown Guide

Best practices for properly shutting down cymongoose servers and cleaning up resources.

## Why Cleanup Matters

The `Manager` object owns C resources that must be explicitly freed:

- Network sockets and connections
- Internal Mongoose event structures
- Memory allocated by the C library
- Timer callbacks

**Not calling `manager.close()` can lead to**:

- Resource leaks (file descriptors, memory)
- Socket CLOSE_WAIT states
- Segfaults if Manager is freed while connections are active

## Basic Pattern: try/finally

Always use `try`/`finally` to ensure cleanup:

```python
from cymongoose import Manager, MG_EV_HTTP_MSG

def handler(conn, ev, data):
    if ev == MG_EV_HTTP_MSG:
        conn.reply(200, b'{"ok":true}')

manager = Manager(handler)
manager.listen('http://0.0.0.0:8000', http=True)

try:
    while True:
        manager.poll(100)
except KeyboardInterrupt:
    print("Shutting down...")
finally:
    manager.close()  # [x] Always called, even on exception
    print("Cleanup complete")
```

## What manager.close() Does

```python
manager.close()
```

1. Closes all open connections
2. Frees all listeners (listening sockets)
3. Cancels all timers
4. Frees internal Mongoose structures
5. Sets `manager._freed = True` to prevent further use

After `close()`, the Manager is unusable:

```python
manager.close()
manager.poll(100)  # [X] RuntimeError: Manager has been freed
```

## Production Pattern: Signal Handlers

For production servers, handle both SIGINT (Ctrl+C) and SIGTERM (systemd, docker):

```python
import signal
from cymongoose import Manager, MG_EV_HTTP_MSG

shutdown_requested = False

def signal_handler(signum, frame):
    global shutdown_requested
    shutdown_requested = True
    signame = "SIGINT" if signum == signal.SIGINT else "SIGTERM"
    print(f"\n{signame} received, shutting down gracefully...")

def handler(conn, ev, data):
    if ev == MG_EV_HTTP_MSG:
        conn.reply(200, b'{"ok":true}')

def main():
    global shutdown_requested

    # Register signal handlers
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    manager = Manager(handler)
    manager.listen('http://0.0.0.0:8000', http=True)
    print("Server started. Press Ctrl+C to stop.")

    try:
        while not shutdown_requested:
            manager.poll(100)
    finally:
        print("Cleaning up...")
        manager.close()
        print("Server stopped cleanly")

if __name__ == "__main__":
    main()
```

## Multi-threaded Pattern

When using background threads with polling:

```python
import threading
from cymongoose import Manager, MG_EV_HTTP_MSG

def handler(conn, ev, data):
    if ev == MG_EV_HTTP_MSG:
        conn.reply(200, b'{"ok":true}')

class Server:
    def __init__(self, port=8000):
        self.port = port
        self.manager = Manager(handler)
        self.stop_flag = threading.Event()
        self.thread = None

    def start(self):
        """Start server in background thread."""
        self.manager.listen(f'http://0.0.0.0:{self.port}', http=True)
        self.thread = threading.Thread(target=self._run, daemon=False)
        self.thread.start()
        print(f"Server started on port {self.port}")

    def _run(self):
        """Background polling loop."""
        while not self.stop_flag.is_set():
            self.manager.poll(100)

    def stop(self):
        """Gracefully stop the server."""
        print("Stopping server...")
        self.stop_flag.set()

        # Wait for polling thread to exit
        if self.thread:
            self.thread.join(timeout=2.0)

        # Clean up Manager
        self.manager.close()
        print("Server stopped")

# Usage
server = Server(8000)
try:
    server.start()
    input("Press Enter to stop...\n")
except KeyboardInterrupt:
    print("\nCtrl+C pressed")
finally:
    server.stop()
```

## Context Manager Pattern (Advanced)

For cleaner code, use a context manager:

```python
from contextlib import contextmanager
from cymongoose import Manager, MG_EV_HTTP_MSG

@contextmanager
def http_server(port, handler):
    """Context manager for cymongoose HTTP server."""
    manager = Manager(handler)
    manager.listen(f'http://0.0.0.0:{port}', http=True)

    try:
        yield manager
    finally:
        manager.close()

# Usage
def handler(conn, ev, data):
    if ev == MG_EV_HTTP_MSG:
        conn.reply(200, b'{"ok":true}')

try:
    with http_server(8000, handler) as manager:
        print("Server running...")
        while True:
            manager.poll(100)
except KeyboardInterrupt:
    print("Shutting down...")
# manager.close() called automatically
```

## Common Mistakes

### [X] DON'T: Forget cleanup

```python
# BAD: No cleanup on exit
manager = Manager(handler)
manager.listen('http://0.0.0.0:8000', http=True)

while True:
    manager.poll(100)  # [X] Ctrl+C leaves resources open
```

### [X] DON'T: Close while polling thread is active

```python
# BAD: Race condition
def run_server():
    while True:
        manager.poll(100)

thread = threading.Thread(target=run_server, daemon=True)
thread.start()

# ... later ...
manager.close()  # [X] Thread might be in poll()! Segfault risk!
```

### [X] DON'T: Reuse closed Manager

```python
# BAD: Manager is single-use
manager = Manager(handler)
manager.listen('http://0.0.0.0:8000', http=True)
manager.close()

manager.listen('http://0.0.0.0:8001', http=True)  # [X] RuntimeError!
```

### [x] DO: Stop polling before closing

```python
# GOOD: Coordinated shutdown
stop_flag = threading.Event()

def run_server():
    while not stop_flag.is_set():
        manager.poll(100)

thread = threading.Thread(target=run_server, daemon=False)
thread.start()

# ... later ...
stop_flag.set()  # Signal thread to stop
thread.join()    # Wait for thread to exit
manager.close()  # [x] Safe to close now
```

## Graceful Shutdown Checklist

1. **Signal shutdown intent**
   - Set flag or call signal handler
   - Use `stop_flag.is_set()` in poll loop

2. **Stop accepting new connections** (optional)
   - Let existing connections finish
   - Implement timeout for long-lived connections

3. **Wait for polling to stop**
   - Join background threads
   - Exit poll loop

4. **Close Manager**
   - Call `manager.close()`
   - Verify cleanup complete

5. **Log shutdown**
   - Confirm clean exit
   - Log any errors

## Example: Complete Production Server

```python
#!/usr/bin/env python3
"""Production-ready cymongoose HTTP server with proper cleanup."""

import signal
import sys
import logging
from cymongoose import Manager, MG_EV_HTTP_MSG

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s'
)
logger = logging.getLogger(__name__)

shutdown_requested = False

def signal_handler(signum, frame):
    """Handle shutdown signals."""
    global shutdown_requested
    shutdown_requested = True
    signame = signal.Signals(signum).name
    logger.info(f"Received {signame}, initiating graceful shutdown")

def handler(conn, ev, data):
    """HTTP request handler."""
    if ev == MG_EV_HTTP_MSG:
        logger.debug(f"{data.method} {data.uri}")
        conn.reply(
            200,
            b'{"status":"ok","message":"Hello from cymongoose"}',
            headers={"Content-Type": "application/json"}
        )

def main():
    global shutdown_requested

    # Parse command line
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8000

    # Register signal handlers
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    # Create and start server
    manager = Manager(handler)

    try:
        manager.listen(f'http://0.0.0.0:{port}', http=True)
        logger.info(f"Server listening on http://0.0.0.0:{port}")
        logger.info("Press Ctrl+C to stop")

        # Main event loop
        while not shutdown_requested:
            manager.poll(100)

        logger.info("Event loop exited")

    except Exception as e:
        logger.error(f"Server error: {e}", exc_info=True)
        return 1

    finally:
        # Cleanup
        logger.info("Closing manager and cleaning up resources...")
        try:
            manager.close()
            logger.info("Cleanup complete")
        except Exception as e:
            logger.error(f"Error during cleanup: {e}", exc_info=True)
            return 1

    logger.info("Server stopped cleanly")
    return 0

if __name__ == "__main__":
    sys.exit(main())
```

## Testing Cleanup

Verify your cleanup works correctly:

```bash
# Start server
python server.py &
SERVER_PID=$!

# Wait for startup
sleep 1

# Send SIGTERM
kill -TERM $SERVER_PID

# Check exit code (should be 0)
wait $SERVER_PID
echo "Exit code: $?"

# Check no leaked file descriptors
lsof -p $SERVER_PID  # Should show "No such process"
```

## Summary

- [x] **Always use try/finally** to ensure `manager.close()` is called
- [x] **Handle both SIGINT and SIGTERM** for production servers
- [x] **Stop polling before closing** in multi-threaded code
- [x] **Log shutdown events** for debugging
- [X] **Never reuse** a closed Manager
- [X] **Never close** while another thread is polling

**Template for new servers**:

```python
manager = Manager(handler)
manager.listen(url, http=True)

try:
    while not shutdown:
        manager.poll(100)
finally:
    manager.close()
```

---

See `poll_timeout_guide.md` for optimizing poll timeout and shutdown responsiveness.
