# Performance Optimization Guide

This guide covers performance tuning and optimization for cymongoose applications.

## Performance Characteristics

### Benchmark Results

Benchmarked with `wrk -t4 -c100 -d10s` on Apple Silicon:

| Framework | Req/sec | Latency (avg) | vs cymongoose |
|---|---|---|---|
| **cymongoose** | **88,710** | **1.13ms** | **baseline** |
| aiohttp | 42,452 | 2.56ms | 2.1x slower |
| FastAPI/uvicorn | 9,989 | 9.96ms | 8.9x slower |
| Flask (threaded) | 1,627 | 22.15ms | 54.5x slower |

## Key Optimizations

### 1. nogil Optimization

Ensure nogil is enabled (default):

```bash
# Check at startup
USE_NOGIL=1  # Should see this message
```

**Impact**: ~88k+ req/sec (vs ~35k with nogil disabled)

See [nogil](nogil.md) for details.

### 2. Poll Timeout

Use 100ms timeout for best balance:

```python
while not shutdown_requested:
    manager.poll(100)  # Optimal timeout
```

| Timeout | Shutdown Response | CPU Usage | Performance |
|---|---|---|---|
| 0ms | Instant | 100% | High |
| **100ms** | **~100ms** | **~0.1%** | **High** |
| 1000ms | ~1 second | ~0.01% | High |
| 5000ms | ~5 seconds | Minimal | High |

**Recommendation**: Use 100ms (responsive + efficient)

### 3. Connection Draining

Use `conn.drain()` instead of `conn.close()`:

```python
# Good: Graceful close
conn.reply(200, b"OK")
conn.drain()  # Flushes send buffer

# Bad: Immediate close (may lose data)
conn.reply(200, b"OK")
conn.close()  # May drop response
```

### 4. Zero-Copy Message Views

Message views (HttpMessage, WsMessage, etc.) provide zero-copy access:

```python
# Zero-copy: No data duplication
def handler(conn, ev, data):
    if ev == MG_EV_HTTP_MSG:
        method = data.method  # View over C struct
        uri = data.uri        # View over C struct
```

### 5. Efficient JSON Parsing

Use Mongoose's lightweight JSON parser for extraction:

```python
from cymongoose import json_get_num, json_get_str

# Fast: Direct extraction without full parse
user_id = json_get_num(json_str, "$.user.id")
name = json_get_str(json_str, "$.user.name")
```

### 6. Buffer Management

Monitor buffer sizes to avoid backpressure:

```python
def handler(conn, ev, data):
    if ev == MG_EV_WRITE:
        if conn.send_len > 100000:  # 100KB
            print("Large send buffer - slow down")

    if conn.is_full:
        # Receive buffer full - backpressure active
        print("Stop reading until buffer clears")
```

## Build Optimizations

### Disable Unused Features

```bash
# Disable TLS if not needed
USE_TLS=0 pip install -e .

# Smaller binary, slightly faster
```

### Compiler Optimizations

```bash
# Release build with optimizations
CFLAGS="-O3 -march=native" pip install -e .
```

## Profiling

### Python Profiling

```python
import cProfile
import pstats

def main():
    manager = Manager(handler)
    manager.listen('http://0.0.0.0:8000', http=True)

    for _ in range(1000):
        manager.poll(0)

cProfile.run('main()', 'profile.stats')

# Analyze
p = pstats.Stats('profile.stats')
p.sort_stats('cumulative').print_stats(20)
```

### Event Tracing

```python
import time

def handler(conn, ev, data):
    start = time.perf_counter()

    # Handle event
    if ev == MG_EV_HTTP_MSG:
        conn.reply(200, b"OK")
        conn.drain()

    elapsed = time.perf_counter() - start
    if elapsed > 0.001:  # > 1ms
        print(f"Slow handler: {elapsed*1000:.2f}ms")
```

## Benchmarking

### Makefile Targets

The project provides several benchmark targets for convenience:

```bash
make bench          # Run quick + load benchmarks (Python client)
make bench-quick    # 1000 sequential requests, no external tools needed
make bench-load     # 5000 requests, 50 concurrent threads
make bench-server   # Start server for manual wrk/ab testing
make bench-compare  # Automated framework comparison (requires ab)
```

The Python-based benchmarks (`bench-quick`, `bench-load`) measure end-to-end
throughput including Python's HTTP client overhead. They are useful for
regression testing but underreport the server's actual capacity by ~20x
due to client-side bottlenecks (connection setup, GIL contention, no
connection reuse).

### Measuring True Server Throughput with wrk

For accurate server performance numbers, use
[wrk](https://github.com/wg/wrk) -- an industry-standard HTTP
benchmarking tool that uses persistent connections and C-level efficiency:

```bash
# Install wrk
brew install wrk  # macOS
# sudo apt-get install wrk  # Linux (Ubuntu/Debian)

# Terminal 1: start the server
make bench-server

# Terminal 2: run the benchmark
wrk -t4 -c100 -d10s http://localhost:8765/
```

Typical output on Apple Silicon:

```text
Running 10s test @ http://localhost:8765/
  4 threads and 100 connections
  Thread Stats   Avg      Stdev     Max   +/- Stdev
    Latency     1.13ms  392.37us  35.36ms   99.60%
    Req/Sec    22.29k   678.03    22.99k    97.28%
  895981 requests in 10.10s, 124.75MB read
Requests/sec:  88710.23
Transfer/sec:     12.35MB
```

### Using Apache Bench

```bash
# 10k requests, 100 concurrent
ab -n 10000 -c 100 http://localhost:8000/
```

### Framework Comparison

To compare cymongoose against other Python frameworks, start each server
in a separate terminal and benchmark with wrk:

```bash
# cymongoose
uv run python tests/benchmarks/servers/pymongoose_server.py 8001
wrk -t4 -c100 -d10s http://localhost:8001/

# aiohttp
uv run python tests/benchmarks/servers/aiohttp_server.py 8002
wrk -t4 -c100 -d10s http://localhost:8002/

# FastAPI/uvicorn
uv run python tests/benchmarks/servers/uvicorn_server.py 8003
wrk -t4 -c100 -d10s http://localhost:8003/

# Flask
uv run python tests/benchmarks/servers/flask_server.py 8004
wrk -t4 -c100 -d10s http://localhost:8004/
```

Or use the automated comparison (requires `ab`):

```bash
make bench-compare
```

## Common Performance Issues

### 1. Slow Shutdown Response

**Symptom**: Takes 5+ seconds to respond to Ctrl+C

**Cause**: Long poll timeout

**Fix**:

```python
# Bad: 5 second timeout
manager.poll(5000)

# Good: 100ms timeout
manager.poll(100)
```

### 2. High CPU Usage

**Symptom**: 100% CPU when idle

**Cause**: Zero poll timeout (busy loop)

**Fix**:

```python
# Bad: Busy loop
manager.poll(0)

# Good: 100ms timeout
manager.poll(100)
```

### 3. Low Throughput

**Symptom**: Lower req/sec than expected

**Causes & Fixes**:

- nogil disabled -- Rebuild with `USE_NOGIL=1`
- Long poll timeout -- Use `poll(100)`
- Slow handler -- Profile and optimize
- Small buffers -- Increase `MG_IO_SIZE` (rebuild required)

### 4. Memory Leaks

**Symptom**: Memory usage grows over time

**Causes**:

- Not removing closed connections from lists
- Storing references to closed connections
- Timer callbacks holding references

**Fix**:

```python
# Remove from client list on close
def handler(conn, ev, data):
    if ev == MG_EV_CLOSE:
        if conn in clients:
            clients.remove(conn)
```

## Scalability

### Single Process

cymongoose can handle 88k+ req/sec in a single process with nogil optimization.

### Multi-Process

For CPU-intensive workloads, use multiple processes:

```bash
# Run 4 processes on different ports
python server.py --port 8000 &
python server.py --port 8001 &
python server.py --port 8002 &
python server.py --port 8003 &

# Load balance with nginx
# See nginx.conf for configuration
```

### Multi-Threading

For I/O-intensive workloads with long-running tasks:

```python
manager = Manager(handler, enable_wakeup=True)

# Offload work to threads
# See threading guide
```

## Best Practices

1. **Enable nogil** (default)
2. **Use poll(100)** for event loop
3. **Use conn.drain()** for graceful close
4. **Monitor buffer sizes** to detect backpressure
5. **Profile regularly** to find bottlenecks
6. **Load test** before production deployment
7. **Scale horizontally** with multiple processes

## See Also

- [nogil optimization details](nogil.md)
- [Multi-threading guide](threading.md)
- [Graceful shutdown patterns](shutdown.md)
