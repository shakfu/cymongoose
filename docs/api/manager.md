# Manager Class

::: cymongoose.Manager
    options:
      members: true
      undoc-members: true
      special-members:
        - **init**
      member-order: bysource

## Overview

The `Manager` class is the core of cymongoose. It manages the Mongoose event loop and all network connections.

## Creating a Manager

```python
from cymongoose import Manager

# With default handler for all connections
def handler(conn, ev, data):
    print(f"Event {ev} on connection {conn.id}")

manager = Manager(handler)

# Without default handler (use per-connection handlers)
manager = Manager()

# With wakeup support for multi-threading
manager = Manager(handler, enable_wakeup=True)
```

### Constructor

::: cymongoose.Manager.**init**
    options:
      members: true

## Listening for Connections

Create server sockets that accept incoming connections.

### HTTP/HTTPS Server

```python
# HTTP server
listener = manager.listen('http://0.0.0.0:8000', http=True)

# HTTPS server (requires TLS initialization)
listener = manager.listen('https://0.0.0.0:8443', http=True)

def handler(conn, ev, data):
    if ev == MG_EV_ACCEPT and conn.is_tls:
        # Initialize TLS on accepted connection
        opts = TlsOpts(cert=cert, key=key)
        conn.tls_init(opts)
```

### TCP/UDP Server

```python
# TCP server
tcp_listener = manager.listen('tcp://0.0.0.0:1234')

# UDP server
udp_listener = manager.listen('udp://0.0.0.0:5678')
```

### MQTT Broker

```python
# MQTT broker
mqtt_listener = manager.mqtt_listen('mqtt://0.0.0.0:1883')
```

### Per-Listener Handler

Override the default handler for specific listeners:

```python
def api_handler(conn, ev, data):
    # Handle API requests
    pass

def ws_handler(conn, ev, data):
    # Handle WebSocket connections
    pass

manager = Manager(default_handler)
manager.listen('http://0.0.0.0:8000', handler=api_handler, http=True)
manager.listen('http://0.0.0.0:9000', handler=ws_handler, http=True)
```

### Methods

::: cymongoose.Manager.listen
    options:
      members: true

::: cymongoose.Manager.mqtt_listen
    options:
      members: true

## Making Connections

Create outbound client connections.

### HTTP/HTTPS Client

```python
def client_handler(conn, ev, data):
    if ev == MG_EV_CONNECT:
        # Send HTTP request
        conn.send(b"GET / HTTP/1.1\r\nHost: example.com\r\n\r\n")
    elif ev == MG_EV_HTTP_MSG:
        print(f"Status: {data.status()}")
        print(f"Body: {data.body_text}")
        conn.close()

# HTTP client
conn = manager.connect('http://example.com:80', client_handler, http=True)

# HTTPS client (TLS auto-initialized)
conn = manager.connect('https://example.com:443', client_handler, http=True)
```

### MQTT Client

```python
def mqtt_handler(conn, ev, data):
    if ev == MG_EV_MQTT_OPEN:
        print("Connected to broker")
        conn.mqtt_sub("sensors/#", qos=1)
    elif ev == MG_EV_MQTT_MSG:
        print(f"{data.topic}: {data.text}")

conn = manager.mqtt_connect(
    'mqtt://broker.hivemq.com:1883',
    handler=mqtt_handler,
    client_id='my-client',
    clean_session=True,
    keepalive=60,
)
```

### SNTP Client

```python
def sntp_handler(conn, ev, data):
    if ev == MG_EV_SNTP_TIME:
        # data is milliseconds since epoch
        print(f"Time: {data} ms")

conn = manager.sntp_connect('udp://time.google.com:123', sntp_handler)
conn.sntp_request()
```

### Methods

::: cymongoose.Manager.connect
    options:
      members: true

::: cymongoose.Manager.mqtt_connect
    options:
      members: true

::: cymongoose.Manager.sntp_connect
    options:
      members: true

## Event Loop

The event loop drives all I/O operations.

### Polling

```python
import signal

shutdown_requested = False

def signal_handler(sig, frame):
    global shutdown_requested
    shutdown_requested = True

signal.signal(signal.SIGINT, signal_handler)

manager = Manager(handler)
manager.listen('http://0.0.0.0:8000', http=True)

# Poll with 100ms timeout
while not shutdown_requested:
    manager.poll(100)

manager.close()
```

### Timeout Guidelines

- **100ms** - Recommended default (responsive shutdown, low CPU)
- **0ms** - Non-blocking (busy loop, 100% CPU)
- **1000ms+** - Longer timeouts (slow shutdown response)

See [Performance](../advanced/performance.md) for details.

### Methods

::: cymongoose.Manager.poll
    options:
      members: true

## Timers

Execute callbacks periodically.

### One-Shot Timer

```python
def callback():
    print("Timer fired!")

# Fire once after 5 seconds
timer = manager.timer_add(5000, callback)
```

### Repeating Timer

```python
def heartbeat():
    print(f"Alive at {time.time()}")

# Fire every second
timer = manager.timer_add(1000, heartbeat, repeat=True)
```

### Immediate Execution

```python
# Run immediately, then repeat every 1 second
timer = manager.timer_add(1000, callback, repeat=True, run_now=True)
```

### Timer Cleanup

Timers are automatically freed when they complete (`MG_TIMER_AUTODELETE` flag). No manual cleanup needed.

### Methods

::: cymongoose.Manager.timer_add
    options:
      members: true

## Multi-threading Support

The `wakeup()` method enables thread-safe communication with the event loop.

### Setup

Enable wakeup support when creating the manager:

```python
manager = Manager(handler, enable_wakeup=True)
```

### Background Worker Pattern

```python
import threading
import queue

# Work queue
work_queue = queue.Queue()
result_queue = queue.Queue()

def worker():
    """Background worker thread."""
    while True:
        work = work_queue.get()
        if work is None:
            break

        # Process work
        result = expensive_computation(work['data'])

        # Send result back via wakeup
        result_queue.put({
            'conn_id': work['conn_id'],
            'result': result,
        })
        manager.wakeup(work['conn_id'], b"result_ready")

# Start worker thread
worker_thread = threading.Thread(target=worker, daemon=True)
worker_thread.start()

def handler(conn, ev, data):
    if ev == MG_EV_HTTP_MSG:
        # Offload to worker
        work_queue.put({
            'conn_id': conn.id,
            'data': data.body_bytes,
        })

    elif ev == MG_EV_WAKEUP:
        # Result ready
        result = result_queue.get()
        conn.reply(200, result['result'])
        conn.drain()
```

See [Threading](../advanced/threading.md) for complete example.

### Methods

::: cymongoose.Manager.wakeup
    options:
      members: true

## Cleanup

Always clean up resources when done.

```python
try:
    while not shutdown_requested:
        manager.poll(100)
finally:
    manager.close()  # Free all resources
```

### Methods

::: cymongoose.Manager.close
    options:
      members: true

## See Also

- `Connection` - Connection management
- [Guide](../guide/index.md) - Protocol-specific guides
- [Threading](../advanced/threading.md) - Multi-threading patterns
