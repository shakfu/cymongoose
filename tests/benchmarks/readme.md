# cymongoose Performance Benchmarks

HTTP server performance benchmarks comparing cymongoose against popular Python web frameworks.

## Quick Start (2 minutes)

```bash
# 1. Install wrk
brew install wrk

# 2. Start server (Terminal 1)
uv run python benchmarks/demo_server.py

# 3. Run benchmark (Terminal 2)
wrk -t4 -c100 -d10s http://localhost:8765/
```

**See [QUICKSTART.md](./QUICKSTART.md) for detailed instructions and expected results.**

---

## Why wrk?

- [x] **Works reliably** on all platforms
- [x] **Industry standard** HTTP benchmarking tool
- [x] **Accurate measurements** of throughput and latency
- [X] Python-based benchmarks have threading/concurrency issues
- [X] Apache Bench (`ab`) has bugs on macOS

## Automated Benchmarks (Experimental)

The automated scripts may have environment-specific issues with concurrent HTTP clients.

### Setup

1. Install dependencies:
```bash
uv add --dev aiohttp fastapi uvicorn flask
```

2. Install wrk (recommended) or Apache Bench:
```bash
brew install wrk apache2-utils
```

### Running
```bash
# Simple test (if environment supports it)
python benchmarks/simple_load_test.py

# Full comparison
python benchmarks/run_benchmark.py
```

## Benchmark Details

- **Test**: Simple JSON response (`{"message": "Hello, World!"}`)
- **Default load**: 50,000 requests, 100 concurrent connections
- **Tool**: Apache Bench (ab)
- **Metrics**: Requests/sec, latency, transfer rate, failed requests

## Servers Tested

1. **cymongoose**: Cython wrapper around Mongoose C library
2. **aiohttp**: Async HTTP server/client framework
3. **uvicorn/FastAPI**: ASGI server with FastAPI framework
4. **Flask**: WSGI framework (sync, threaded mode)

## Expected Performance Characteristics

- **cymongoose**: High throughput, low latency (C-based event loop)
- **aiohttp/uvicorn**: Good async performance, pure Python overhead
- **Flask**: Lower throughput (sync, thread overhead)

## Notes

- Tests run single-process servers (no workers/multiprocessing)
- Results depend on CPU cores, OS scheduling, network stack
- Benchmarks measure raw HTTP performance, not application logic
- For production: consider multi-worker setups, connection pooling, caching
