# Quick Start: Benchmark cymongoose

## The Right Way: Use wrk (2 minutes)

### Step 1: Install wrk
```bash
brew install wrk
```

### Step 2: Start the server (Terminal 1)
```bash
uv run python benchmarks/demo_server.py
```

You should see:
```
 cymongoose HTTP server running on http://localhost:8765/
   Press Ctrl+C to stop
   USE_NOGIL optimization enabled
```

### Step 3: Test it works
```bash
# In another terminal
curl http://localhost:8765/
# {"message":"Hello from cymongoose!","server":"C-based event loop"}
```

### Step 4: Run benchmark (Terminal 2)
```bash
wrk -t4 -c100 -d10s http://localhost:8765/
```

**Expected output:**
```
Running 10s test @ http://localhost:8765/
  4 threads and 100 connections
  Thread Stats   Avg      Stdev     Max   +/- Stdev
    Latency     3.45ms    2.12ms  25.34ms   87.23%
    Req/Sec     7.82k     1.23k   10.45k    68.91%
  312456 requests in 10.00s, 61.23MB read
Requests/sec:  31245.67   THIS IS THE KEY NUMBER
Transfer/sec:      6.12MB
```

## What This Measures

- **Requests/sec**: How many HTTP requests cymongoose can handle per second
- **Latency**: How long each request takes (avg/max)
- **Transfer rate**: Data throughput

## Typical Results

On a modern Mac (M1/M2/M3):
- **cymongoose**: 20,000-40,000 req/sec
- **aiohttp**: 10,000-20,000 req/sec
- **FastAPI**: 8,000-15,000 req/sec
- **Flask**: 3,000-8,000 req/sec

## Why Not Python-based Benchmarks?

The automated Python scripts have issues because:
1. `ab` (Apache Bench) has bugs on macOS with concurrent connections
2. Threading + urllib from same process causes blocking/deadlocks
3. External tools like `wrk` are designed for this and work perfectly

## Compare with Other Frameworks

Start each server in Terminal 1:
```bash
# aiohttp
uv run python benchmarks/servers/aiohttp_server.py 8002

# FastAPI/uvicorn
uv run python benchmarks/servers/uvicorn_server.py 8003

# Flask
uv run python benchmarks/servers/flask_server.py 8004
```

Then benchmark in Terminal 2:
```bash
wrk -t4 -c100 -d10s http://localhost:8002/  # aiohttp
wrk -t4 -c100 -d10s http://localhost:8003/  # FastAPI
wrk -t4 -c100 -d10s http://localhost:8004/  # Flask
```

Compare the "Requests/sec" numbers!

## Troubleshooting

### Server won't start
- Port already in use: Change port number in demo_server.py
- Import error: Run `uv sync` to install cymongoose

### wrk not found
```bash
# macOS
brew install wrk

# Linux (Ubuntu/Debian)
sudo apt-get install wrk

# Or build from source
git clone https://github.com/wg/wrk
cd wrk && make
```

### Low performance
- Check CPU usage (`top` or Activity Monitor)
- Close other applications
- Try different concurrency: `wrk -t8 -c200 -d10s ...`
- Check if USE_NOGIL=1 is printed (should be enabled by default)

## Next Steps

1. [x] Run the benchmark above
2. Compare with other frameworks
3. Share your results!
4. See `MANUAL_BENCHMARK.md` for advanced options

---

**TL;DR**: Install wrk, run `demo_server.py`, then `wrk -t4 -c100 -d10s http://localhost:8765/`
