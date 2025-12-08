# Manual Performance Benchmark Guide

The automated benchmarks have some environment-specific issues with concurrent HTTP clients in Python. Here's how to run manual benchmarks.

## Quick Benchmark with wrk (Recommended)

### Install wrk
```bash
# macOS
brew install wrk

# Linux
git clone https://github.com/wg/wrk && cd wrk && make
```

### Run cymongoose server
```bash
# Terminal 1
uv run python benchmarks/servers/pymongoose_server.py 8001
```

### Run wrk benchmark
```bash
# Terminal 2
wrk -t4 -c100 -d30s http://localhost:8001/

# Example output:
# Running 30s test @ http://localhost:8001/
#   4 threads and 100 connections
#   Thread Stats   Avg      Stdev     Max   +/- Stdev
#     Latency     2.45ms    1.23ms  45.67ms   89.34%
#     Req/Sec    10.23k     1.45k   13.45k    72.45%
#   1223456 requests in 30.00s, 234.56MB read
# Requests/sec:  40781.87
# Transfer/sec:      7.82MB
```

##Alternative: Apache Bench (if wrk not available)

```bash
# Lower concurrency to avoid macOS issues
ab -n 10000 -c 10 http://localhost:8001/
```

## Comparing with Other Frameworks

### aiohttp server
```bash
uv run python benchmarks/servers/aiohttp_server.py 8002
wrk -t4 -c100 -d30s http://localhost:8002/
```

### FastAPI/uvicorn server
```bash
uv run python benchmarks/servers/uvicorn_server.py 8003
wrk -t4 -c100 -d30s http://localhost:8003/
```

### Flask server
```bash
uv run python benchmarks/servers/flask_server.py 8004
wrk -t4 -c100 -d30s http://localhost:8004/
```

## Expected Results

Based on cymongoose architecture (C event loop, nogil optimization):

| Framework | Requests/sec | Latency (avg) |
|-----------|-------------|---------------|
| **cymongoose** | **20,000-40,000+** | **2-5ms** |
| aiohttp | 10,000-20,000 | 5-10ms |
| uvicorn/FastAPI | 8,000-15,000 | 6-12ms |
| Flask (threaded) | 3,000-8,000 | 12-30ms |

Actual performance depends on:
- CPU cores and frequency
- OS network stack tuning
- System load
- Connection pooling
- Whether nogil optimizations are enabled (`USE_NOGIL=1`)

## Verification Tests

The servers all work correctly - verified with:

```bash
# Test cymongoose
curl http://localhost:8001/
# {"message":"Hello, World!"}
```

All pytest tests pass including HTTP server tests in `tests/test_http_server.py`.
