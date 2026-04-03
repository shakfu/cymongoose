# Graceful Shutdown Guide

This guide covers proper shutdown handling for production cymongoose applications.

## Why Signal Handlers?

With nogil optimization enabled, `KeyboardInterrupt` from Ctrl+C may not be caught reliably during `poll()`:

```python
# DON'T: May not catch Ctrl+C reliably
try:
    while True:
        manager.poll(100)  # GIL released - signals deferred
except KeyboardInterrupt:
    pass

# DO: Use signal handlers
import signal

shutdown_requested = False

def signal_handler(sig, frame):
    global shutdown_requested
    shutdown_requested = True

signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)

while not shutdown_requested:
    manager.poll(100)
```

## Basic Pattern

```python
import signal
from cymongoose import Manager

shutdown_requested = False

def signal_handler(sig, frame):
    """Handle shutdown signals."""
    global shutdown_requested
    shutdown_requested = True

def main():
    global shutdown_requested

    # Register signal handlers
    signal.signal(signal.SIGINT, signal_handler)  # Ctrl+C
    signal.signal(signal.SIGTERM, signal_handler)  # kill command

    # Create manager and listen
    manager = Manager(handler)
    manager.listen('http://0.0.0.0:8000', http=True)

    print("Server running on http://0.0.0.0:8000")
    print("Press Ctrl+C to stop")

    try:
        while not shutdown_requested:
            manager.poll(100)
        print("Shutting down...")
    finally:
        manager.close()
        print("Server stopped cleanly")

if __name__ == "__main__":
    main()
```

## AsyncManager Shutdown

When using ``AsyncManager``, shutdown is handled automatically by
``__aexit__``. The ``shutdown_timeout`` parameter (default 30 seconds)
controls how long it waits for the poll thread to stop:

1. ``__aexit__`` signals the thread to stop and sends a wakeup.
2. Waits 5 seconds for the thread to join.
3. If still alive: emits a ``RuntimeWarning``, retries the wakeup,
   and waits another 5 seconds.
4. Repeats step 3 until ``shutdown_timeout`` is reached.
5. At the hard limit: emits a final warning and moves on without
   calling ``Manager.close()``.

```python
# Tune the timeout for your application
async with AsyncManager(handler, shutdown_timeout=10) as am:
    am.listen("http://0.0.0.0:8080")
    # ...
# __aexit__ handles shutdown automatically
```

The warnings surface in logs so operators can identify blocked handlers.
If a handler finishes before the timeout, shutdown completes normally
and ``Manager.close()`` is called.

## Connection Draining

### Use `conn.drain()` Instead of `conn.close()`

```python
def handler(conn, ev, data):
    if ev == MG_EV_HTTP_MSG:
        conn.reply(200, b"Goodbye!")

        # Good: Graceful close
        conn.drain()  # Flushes send buffer before closing

        # Bad: Immediate close (may lose data)
        # conn.close()  # DON'T use this
```

### What `drain()` Does

1. Sets `is_draining = 1`
2. Stops reading from socket
3. Continues sending buffered data
4. Closes connection when send buffer is empty

## Server Shutdown

### Close Active Connections

```python
clients = []

def handler(conn, ev, data):
    if ev == MG_EV_ACCEPT:
        clients.append(conn)

    elif ev == MG_EV_CLOSE:
        if conn in clients:
            clients.remove(conn)

try:
    while not shutdown_requested:
        manager.poll(100)

    # Close all active connections
    print(f"Closing {len(clients)} active connections...")
    for client in clients[:]:
        try:
            client.reply(503, b"Server shutting down")
            client.drain()
        except RuntimeError:
            pass  # Already closed

    # Give time for draining
    for _ in range(10):  # Up to 1 second
        manager.poll(100)
        if not clients:
            break

finally:
    manager.close()
```

## Background Workers

### Stop Worker Threads

```python
import threading
import queue

work_queue = queue.Queue()
worker_threads = []

def worker():
    while True:
        work = work_queue.get()
        if work is None:  # Poison pill
            break
        process_work(work)

# Start workers
for _ in range(4):
    t = threading.Thread(target=worker, daemon=True)
    t.start()
    worker_threads.append(t)

def signal_handler(sig, frame):
    global shutdown_requested
    shutdown_requested = True

    # Stop workers with poison pills
    for _ in worker_threads:
        work_queue.put(None)

try:
    while not shutdown_requested:
        manager.poll(100)

    # Wait for workers to finish
    print("Waiting for workers...")
    for thread in worker_threads:
        thread.join(timeout=5.0)

finally:
    manager.close()
```

## Timers

One-shot timers are automatically freed after firing (`MG_TIMER_AUTODELETE` flag).
Repeating timers can be stopped early with `cancel()`, or they are freed when
the manager closes:

```python
timer = manager.timer_add(1000, callback, repeat=True)

# Option 1: Cancel explicitly (thread-safe, can be called from any thread)
timer.cancel()

# Option 2: Let manager.close() free all remaining timers
manager.close()
```

## Systemd Integration

### Service File

```ini
# /etc/systemd/system/myapp.service
[Unit]
Description=cymongoose Application
After=network.target

[Service]
Type=simple
User=www-data
WorkingDirectory=/opt/myapp
ExecStart=/opt/myapp/venv/bin/python server.py
Restart=on-failure

# Shutdown timeout
TimeoutStopSec=30

# Signals
KillMode=mixed
KillSignal=SIGTERM

[Install]
WantedBy=multi-user.target
```

### Enable and Start

```bash
sudo systemctl daemon-reload
sudo systemctl enable myapp
sudo systemctl start myapp

# Check status
sudo systemctl status myapp

# View logs
sudo journalctl -u myapp -f

# Stop gracefully
sudo systemctl stop myapp
```

## Docker Integration

### Dockerfile

```dockerfile
FROM python:3.11-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .

# Signal handling works with ENTRYPOINT
ENTRYPOINT ["python", "server.py"]
```

### Docker Compose

```yaml
version: '3.8'

services:
  app:
    build: .
    ports:
      - "8000:8000"
    restart: unless-stopped

    # Graceful shutdown timeout
    stop_grace_period: 30s
```

### Run

```bash
# Start
docker-compose up -d

# Stop gracefully
docker-compose stop  # Sends SIGTERM

# View logs
docker-compose logs -f
```

## Handling Long-Running Requests

### Request Timeout

```python
import time

connections_with_timeout = {}  # {conn_id: start_time}

def handler(conn, ev, data):
    if ev == MG_EV_HTTP_MSG:
        connections_with_timeout[conn.id] = time.time()

        # Start processing
        process_request(conn, data)

    elif ev == MG_EV_CLOSE:
        if conn.id in connections_with_timeout:
            del connections_with_timeout[conn.id]

# Check for timeouts periodically
def check_timeouts():
    now = time.time()
    for conn_id, start_time in list(connections_with_timeout.items()):
        if now - start_time > 30:  # 30 second timeout
            conn = connections.get(conn_id)
            if conn:
                conn.reply(408, b"Request Timeout")
                conn.drain()

manager.timer_add(1000, check_timeouts, repeat=True)
```

## Best Practices

1. **Use signal handlers**, not try/except for Ctrl+C
2. **Handle SIGTERM** for systemd/Docker compatibility
3. **Use conn.drain()**, not conn.close()
4. **Close active connections** on shutdown
5. **Stop worker threads** with poison pills
6. **Set timeouts** for graceful shutdown (30 seconds)
7. **Test shutdown** under load

## Common Issues

### Ctrl+C Not Working

**Cause**: Using try/except instead of signal handlers

**Fix**: Use signal handlers (see basic pattern above)

### Connections Not Closing

**Cause**: Using `conn.close()` instead of `conn.drain()`

**Fix**: Use `conn.drain()` for graceful close

### Shutdown Takes Too Long

**Causes**:

- Long poll timeout
- Connections not draining
- Workers not stopping

**Fixes**:

- Use `poll(100)`
- Use `conn.drain()`
- Send poison pills to workers
- Set timeouts

## See Also

- [Why signal handlers are needed](nogil.md)
- [Poll timeout recommendations](performance.md)
- [Connection draining patterns](../guide/index.md)
