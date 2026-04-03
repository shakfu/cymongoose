#!/usr/bin/env python3
"""Benchmark the micro web-framework routing overhead.

Compares three configurations against the same workload:

1. **Raw handler** -- inline ``if event == MG_EV_HTTP_MSG: reply()``.
   Baseline with zero Python routing overhead.
2. **Framework (static route)** -- ``@app.get("/")`` matching a single
   fixed path.  Measures regex-match + Request/Response wrapper cost.
3. **Framework (parameterised route)** -- ``@app.get("/items/<int:id>")``
   with type conversion.  Measures the full routing pipeline.

Each configuration is tested sequentially and then under concurrency so
you can see both latency and throughput characteristics.

Usage:
    uv run python tests/benchmarks/bench_web_framework.py

For more accurate throughput numbers, use wrk against the demo servers:

    # Terminal 1 -- raw handler
    uv run python tests/benchmarks/bench_web_framework.py --serve raw

    # Terminal 1 -- framework
    uv run python tests/benchmarks/bench_web_framework.py --serve framework

    # Terminal 2
    wrk -t4 -c100 -d10s http://localhost:8765/
"""

import argparse
import platform
import signal
import socket
import statistics
import sys
import threading
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))
sys.path.insert(0, str(Path(__file__).parent.parent / "examples" / "http"))

from cymongoose import MG_EV_HTTP_MSG, Manager

from http_web_framework import App, Response, json_response

# ---------------------------------------------------------------------------
# Server configurations
# ---------------------------------------------------------------------------

JSON_BODY = b'{"message":"Hello, World!"}'
JSON_HEADERS = {"Content-Type": "application/json"}


def make_raw_server(port):
    """Bare cymongoose handler -- no framework."""

    def handler(conn, ev, data):
        if ev == MG_EV_HTTP_MSG:
            conn.reply(200, JSON_BODY, headers=JSON_HEADERS)

    mgr = Manager(handler)
    mgr.listen(f"http://0.0.0.0:{port}")
    return mgr


def make_framework_server(port):
    """Framework with a single static route."""
    app = App()

    @app.get("/")
    def index(req):
        return Response(JSON_BODY, headers=JSON_HEADERS)

    mgr = Manager(app.handler)
    mgr.listen(f"http://0.0.0.0:{port}")
    return mgr


def make_framework_param_server(port):
    """Framework with a parameterised route."""
    app = App()

    @app.get("/items/<int:id>")
    def get_item(req, id):
        return json_response({"id": id, "message": "Hello, World!"})

    mgr = Manager(app.handler)
    mgr.listen(f"http://0.0.0.0:{port}")
    return mgr


# ---------------------------------------------------------------------------
# Benchmark harness
# ---------------------------------------------------------------------------

def get_free_port():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def make_request(url):
    start = time.perf_counter()
    try:
        resp = urllib.request.urlopen(url, timeout=5)
        resp.read()
        return (True, time.perf_counter() - start)
    except Exception:
        return (False, time.perf_counter() - start)


def run_sequential(url, n):
    latencies = []
    for _ in range(n):
        ok, dur = make_request(url)
        if ok:
            latencies.append(dur)
    return latencies


def run_concurrent(url, n, concurrency):
    latencies = []
    with ThreadPoolExecutor(max_workers=concurrency) as pool:
        futures = [pool.submit(make_request, url) for _ in range(n)]
        for f in as_completed(futures):
            ok, dur = f.result()
            if ok:
                latencies.append(dur)
    return latencies


def percentile(data, p):
    k = (len(data) - 1) * (p / 100)
    f = int(k)
    c = f + 1
    if c >= len(data):
        return data[-1]
    return data[f] + (k - f) * (data[c] - data[f])


def report(label, latencies, wall_time):
    if not latencies:
        print(f"  {label}: no successful requests")
        return
    latencies.sort()
    n = len(latencies)
    rps = n / wall_time
    avg = statistics.mean(latencies) * 1000
    p50 = percentile(latencies, 50) * 1000
    p95 = percentile(latencies, 95) * 1000
    p99 = percentile(latencies, 99) * 1000
    mn = latencies[0] * 1000
    mx = latencies[-1] * 1000
    print(f"  {label}")
    print(f"    Requests:    {n}")
    print(f"    Req/sec:     {rps:,.0f}")
    print(f"    Latency avg: {avg:.2f} ms")
    print(f"    Latency p50: {p50:.2f} ms | p95: {p95:.2f} ms | p99: {p99:.2f} ms")
    print(f"    Min/Max:     {mn:.2f} / {mx:.2f} ms")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def run_benchmarks():
    is_windows = platform.system() == "Windows"
    seq_n = 200 if is_windows else 1000
    conc_n = 500 if is_windows else 3000
    concurrency = 20 if is_windows else 50

    configs = [
        ("Raw handler", make_raw_server, "/"),
        ("Framework (static route)", make_framework_server, "/"),
        ("Framework (param route)", make_framework_param_server, "/items/42"),
    ]

    all_results = {}

    for name, factory, path in configs:
        port = get_free_port()
        mgr = factory(port)
        stop = threading.Event()

        def poll_loop(m=mgr, s=stop):
            while not s.is_set():
                m.poll(50)

        t = threading.Thread(target=poll_loop, daemon=True)
        t.start()
        time.sleep(0.3)

        url = f"http://127.0.0.1:{port}{path}"

        # Warmup
        for _ in range(20):
            make_request(url)

        print(f"\n--- {name} ---")

        # Sequential
        wall_start = time.perf_counter()
        lats = run_sequential(url, seq_n)
        wall = time.perf_counter() - wall_start
        report(f"Sequential ({seq_n} reqs)", lats, wall)
        seq_rps = len(lats) / wall if lats else 0

        # Concurrent
        wall_start = time.perf_counter()
        lats = run_concurrent(url, conc_n, concurrency)
        wall = time.perf_counter() - wall_start
        report(f"Concurrent ({conc_n} reqs, {concurrency} workers)", lats, wall)
        conc_rps = len(lats) / wall if lats else 0

        all_results[name] = (seq_rps, conc_rps)

        stop.set()
        t.join(timeout=2)
        mgr.close()

    # Summary
    print("\n" + "=" * 65)
    print("SUMMARY")
    print("=" * 65)
    print(f"{'Configuration':<32} {'Seq req/s':>10} {'Conc req/s':>12}")
    print("-" * 65)

    raw_seq, raw_conc = all_results.get("Raw handler", (1, 1))
    for name, (seq, conc) in all_results.items():
        seq_pct = (seq / raw_seq * 100) if raw_seq else 0
        conc_pct = (conc / raw_conc * 100) if raw_conc else 0
        print(f"  {name:<30} {seq:>9,.0f} {conc:>11,.0f}  "
              f"({seq_pct:.0f}% / {conc_pct:.0f}%)")

    print("-" * 65)
    print("  Percentages are relative to raw handler (100% = no overhead)")
    print()
    print("NOTE: Python HTTP clients underreport server capacity (~20x).")
    print("For accurate throughput, use wrk:")
    print("  uv run python tests/benchmarks/bench_web_framework.py --serve framework")
    print("  wrk -t4 -c100 -d10s http://localhost:8765/")


def serve_mode(mode):
    """Start a single server for manual benchmarking with wrk/ab."""
    port = 8765
    if mode == "raw":
        mgr = make_raw_server(port)
        label = "Raw handler"
    elif mode == "framework":
        mgr = make_framework_server(port)
        label = "Framework (static route)"
    else:
        mgr = make_framework_param_server(port)
        label = "Framework (param route)"

    shutdown = False

    def on_signal(sig, frame):
        nonlocal shutdown
        shutdown = True

    signal.signal(signal.SIGINT, on_signal)
    signal.signal(signal.SIGTERM, on_signal)

    print(f"{label} on http://localhost:{port}/")
    print("Press Ctrl+C to stop")
    try:
        while not shutdown:
            mgr.poll(100)
    finally:
        mgr.close()
        print("Stopped.")


def main():
    parser = argparse.ArgumentParser(description="Web framework benchmark")
    parser.add_argument(
        "--serve", choices=["raw", "framework", "framework-param"],
        help="Start a single server for manual wrk/ab testing instead of running benchmarks",
    )
    args = parser.parse_args()

    if args.serve:
        serve_mode(args.serve)
    else:
        run_benchmarks()


if __name__ == "__main__":
    main()
