# cymongoose Performance Benchmarks

HTTP server performance benchmarks comparing cymongoose against popular Python web
frameworks using [wrk](https://github.com/wg/wrk).

---

## Quick Start

```bash
# 1. Install wrk
brew install wrk          # macOS
# sudo apt-get install wrk  # Linux (Ubuntu/Debian)

# 2. Start server (Terminal 1)
uv run python tests/benchmarks/demo_server.py

# 3. Run benchmark (Terminal 2)
wrk -t4 -c100 -d10s http://localhost:8765/
```

### Why wrk?

- Industry-standard HTTP benchmarking tool
- Accurate measurements of throughput and latency
- Python-based HTTP benchmarks have threading/concurrency issues
- Apache Bench (`ab`) has bugs on macOS with concurrent connections

---

## Results

**Test configuration:** Apple Silicon Mac, wrk with 4 threads, 100 concurrent connections,
10-second duration. All servers return an identical JSON response
(`{"message":"Hello, World!"}`).

| Framework | Req/sec | Speedup | Latency (avg) | Architecture |
|-----------|---------|---------|---------------|--------------|
| **cymongoose** | **60,973** | **1.00x** | **1.67ms** | C event loop + Cython + nogil |
| aiohttp | 42,452 | 0.70x | 2.56ms | Python async (asyncio) |
| FastAPI | 9,989 | 0.16x | 9.96ms | Python ASGI (uvicorn) |
| Flask | 1,627 | 0.03x | 22.15ms | Python WSGI (threaded) |

```text
Requests/sec (higher = better):

cymongoose  ########################################  60,973
aiohttp     ###########################              42,452
FastAPI     ######                                     9,989
Flask       #                                          1,627
            0      10k     20k     30k     40k     50k     60k
```

### Key Findings

1. **C-level performance in Python** -- 60,973 req/sec puts cymongoose in the same
   league as nginx (50k-100k), Go net/http (40k-80k), and Node.js (20k-40k).
2. **6--37x faster than pure Python** -- FastAPI 6.1x slower, Flask 37.5x slower.
3. **Beats async Python** -- 1.44x faster than aiohttp (best async Python framework).
4. **Consistent low latency** -- 1.67ms average, 99.8% of requests under 2.74ms.
5. **Zero errors under load** -- Flask had 81 connection errors at 100 concurrent
   connections; cymongoose, aiohttp, and FastAPI had none.

---

## Running Framework Comparisons

Start each server in a separate terminal and benchmark with wrk:

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

### Automated Scripts (Experimental)

The automated Python-based scripts may have environment-specific issues with concurrent
HTTP clients. Prefer wrk for reliable results.

```bash
# Simple test
python tests/benchmarks/simple_load_test.py

# Full comparison
python tests/benchmarks/run_benchmark.py
```

Automated scripts require extra dependencies: `uv add --dev aiohttp fastapi uvicorn flask`

---

## Why cymongoose Is Fast

1. **Mongoose C library** -- battle-tested embedded networking with hand-optimized event loop.
2. **Cython bindings** -- near-zero overhead Python-to-C calls, direct memory access to
   C structs.
3. **nogil optimization** -- 21 methods release the GIL for true parallel processing.
4. **Event-driven architecture** -- single-threaded, non-blocking I/O, no context switching.
5. **Zero-copy design** -- HttpMessage/WsMessage wrap C pointers directly; no data copying
   until the user accesses a property.

---

## Detailed wrk Output

<details>
<summary>cymongoose: 60,973 req/sec</summary>

```text
wrk -t4 -c100 -d10s http://localhost:8765/
Running 10s test @ http://localhost:8765/
  4 threads and 100 connections
  Thread Stats   Avg      Stdev     Max   +/- Stdev
    Latency     1.67ms    1.07ms  60.14ms   99.80%
    Req/Sec    15.32k   452.36    15.64k    99.01%
  615911 requests in 10.10s, 85.76MB read
Requests/sec:  60972.51
Transfer/sec:      8.49MB
```
</details>

<details>
<summary>aiohttp: 42,452 req/sec</summary>

```text
wrk -t4 -c100 -d10s http://localhost:8002/
Running 10s test @ http://localhost:8002/
  4 threads and 100 connections
  Thread Stats   Avg      Stdev     Max   +/- Stdev
    Latency     2.56ms    2.64ms  54.24ms   98.95%
    Req/Sec    10.67k   718.30    11.06k    96.04%
  428865 requests in 10.10s, 76.48MB read
Requests/sec:  42451.62
Transfer/sec:      7.57MB
```
</details>

<details>
<summary>FastAPI: 9,989 req/sec</summary>

```text
wrk -t4 -c100 -d10s http://localhost:8003/
Running 10s test @ http://localhost:8003/
  4 threads and 100 connections
  Thread Stats   Avg      Stdev     Max   +/- Stdev
    Latency     9.96ms  581.91us  23.89ms   97.49%
    Req/Sec     2.52k   159.67     4.69k    98.01%
  100934 requests in 10.10s, 14.63MB read
Requests/sec:   9988.83
Transfer/sec:      1.45MB
```
</details>

<details>
<summary>Flask: 1,627 req/sec</summary>

```text
wrk -t4 -c100 -d10s http://localhost:8004/
Running 10s test @ http://localhost:8004/
  4 threads and 100 connections
  Thread Stats   Avg      Stdev     Max   +/- Stdev
    Latency    22.15ms    1.73ms  45.40ms   97.10%
    Req/Sec     1.11k   132.31     1.22k    94.59%
  16380 requests in 10.07s, 3.01MB read
  Socket errors: connect 81, read 0, write 0, timeout 0
Requests/sec:   1627.14
Transfer/sec:    306.68KB
```
</details>

---

## Troubleshooting

- **Port already in use:** Change the port number in the server command.
- **Import error:** Run `uv sync` to build and install cymongoose.
- **wrk not found:** `brew install wrk` (macOS) or build from source:
  `git clone https://github.com/wg/wrk && cd wrk && make`
- **Low performance:** Close other applications, try `wrk -t8 -c200 -d10s ...`,
  verify `USE_NOGIL` is enabled.

---

## Caveats

- Benchmarks are self-reported; results depend on CPU, OS, and system load.
- The wrk test measures a trivial JSON response; real-world workloads with business logic
  in Python handlers will be dominated by Python execution time, not C overhead.
- The Flask comparison is somewhat unfair (sync WSGI vs event-driven); a fairer comparison
  would use Gunicorn with multiple workers.
- All servers run single-process (no workers/multiprocessing).

---

*Tested on Apple Silicon Mac with wrk. Your results may vary based on hardware and configuration.*
