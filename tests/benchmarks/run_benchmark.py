#!/usr/bin/env python3
"""
Performance benchmark runner for cymongoose HTTP server.

Compares cymongoose against popular Python web frameworks:
- aiohttp (async)
- FastAPI/uvicorn (async)
- Flask (sync)

Uses Apache Bench (ab) for HTTP load testing.
"""

import subprocess
import sys
import time
import signal
from pathlib import Path
from typing import Dict, List, Optional


SERVERS = {
    "cymongoose": {"script": "pymongoose_server.py", "port": 8001},
    "aiohttp": {"script": "aiohttp_server.py", "port": 8002},
    "uvicorn": {"script": "uvicorn_server.py", "port": 8003},
    "flask": {"script": "flask_server.py", "port": 8004},
}


def check_dependencies():
    """Check if required tools are available."""
    # Check for ab (Apache Bench)
    try:
        subprocess.run(["ab", "-V"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
    except (subprocess.CalledProcessError, FileNotFoundError):
        print("ERROR: Apache Bench (ab) not found.")
        print("Install with: brew install apache2-utils (macOS)")
        sys.exit(1)

    # Check Python dependencies
    missing = []
    try:
        import aiohttp
    except ImportError:
        missing.append("aiohttp")

    try:
        import fastapi
        import uvicorn
    except ImportError:
        missing.append("fastapi uvicorn")

    try:
        import flask
    except ImportError:
        missing.append("flask")

    if missing:
        print(f"Missing Python dependencies: {', '.join(missing)}")
        print(f"Install with: uv add --dev {' '.join(missing)}")
        sys.exit(1)


def start_server(name: str, script: str, port: int) -> subprocess.Popen:
    """Start a server process."""
    script_path = Path(__file__).parent / "servers" / script

    # Use sys.executable directly (will be python from uv run)
    proc = subprocess.Popen(
        [sys.executable, str(script_path), str(port)],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,  # Line buffered
    )

    # Wait for server to start
    time.sleep(3)

    # Check if process crashed
    if proc.poll() is not None:
        stdout, _ = proc.communicate()
        print(f"ERROR: {name} server crashed on startup")
        print(f"Output: {stdout}")
        sys.exit(1)

    # Check if server is running
    try:
        result = subprocess.run(
            ["curl", "-s", f"http://localhost:{port}/"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=2,
            check=True,
        )
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as e:
        print(f"ERROR: {name} server failed to respond on port {port}")
        stdout, _ = proc.communicate(timeout=1) if proc.poll() is None else (None, None)
        if stdout:
            print(f"Server output: {stdout[:500]}")
        proc.terminate()
        sys.exit(1)

    return proc


def stop_server(proc: subprocess.Popen):
    """Stop a server process."""
    try:
        proc.terminate()
        proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait()


def run_benchmark(url: str, requests: int = 10000, concurrency: int = 100) -> Dict[str, float]:
    """Run Apache Bench and parse results."""
    cmd = [
        "ab",
        "-n",
        str(requests),
        "-c",
        str(concurrency),
        "-q",  # Quiet mode
        url,
    ]

    result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

    if result.returncode != 0:
        print(f"ERROR: ab failed: {result.stderr}")
        return {}

    # Parse output
    output = result.stdout
    metrics = {}

    for line in output.split("\n"):
        if "Requests per second:" in line:
            metrics["req_per_sec"] = float(line.split()[3])
        elif "Time per request:" in line and "mean" in line:
            metrics["time_per_req_mean"] = float(line.split()[3])
        elif "Time per request:" in line and "across all" in line:
            metrics["time_per_req_concurrent"] = float(line.split()[3])
        elif "Transfer rate:" in line:
            metrics["transfer_rate_kb"] = float(line.split()[2])
        elif "Failed requests:" in line:
            metrics["failed"] = int(line.split()[2])

    return metrics


def format_results(results: Dict[str, Dict[str, float]]):
    """Format and print benchmark results."""
    print("\n" + "=" * 80)
    print("BENCHMARK RESULTS")
    print("=" * 80)

    # Header
    print(f"\n{'Server':<15} {'Req/sec':<12} {'Latency (ms)':<15} {'Failed':<10}")
    print("-" * 80)

    # Sort by requests per second
    sorted_results = sorted(results.items(), key=lambda x: x[1].get("req_per_sec", 0), reverse=True)

    baseline = None
    for name, metrics in sorted_results:
        req_per_sec = metrics.get("req_per_sec", 0)
        latency = metrics.get("time_per_req_mean", 0)
        failed = metrics.get("failed", 0)

        line = f"{name:<15} {req_per_sec:<12.2f} {latency:<15.2f} {failed:<10}"

        # Calculate percentage vs baseline (fastest)
        if baseline is None:
            baseline = req_per_sec
            line += " (baseline)"
        else:
            pct = (req_per_sec / baseline) * 100
            line += f" ({pct:.1f}% of baseline)"

        print(line)

    print("\n" + "=" * 80)


def main():
    """Run benchmarks for all servers."""
    import argparse

    parser = argparse.ArgumentParser(description="Benchmark cymongoose HTTP server")
    parser.add_argument(
        "-n",
        "--requests",
        type=int,
        default=50000,
        help="Total number of requests (default: 50000)",
    )
    parser.add_argument(
        "-c",
        "--concurrency",
        type=int,
        default=100,
        help="Number of concurrent requests (default: 100)",
    )
    parser.add_argument(
        "-s",
        "--servers",
        nargs="+",
        choices=list(SERVERS.keys()),
        default=list(SERVERS.keys()),
        help="Servers to benchmark (default: all)",
    )

    args = parser.parse_args()

    print("Checking dependencies...")
    check_dependencies()

    print(f"\nBenchmark configuration:")
    print(f"  Total requests: {args.requests:,}")
    print(f"  Concurrency: {args.concurrency}")
    print(f"  Servers: {', '.join(args.servers)}")

    results = {}

    for name in args.servers:
        config = SERVERS[name]
        print(f"\n{'=' * 80}")
        print(f"Benchmarking {name}...")
        print(f"{'=' * 80}")

        # Start server
        print(f"Starting {name} server on port {config['port']}...")
        proc = start_server(name, config["script"], config["port"])

        try:
            # Run benchmark
            print(
                f"Running benchmark ({args.requests:,} requests, {args.concurrency} concurrent)..."
            )
            metrics = run_benchmark(
                f"http://localhost:{config['port']}/", args.requests, args.concurrency
            )

            if metrics:
                results[name] = metrics
                print(f"  Requests/sec: {metrics.get('req_per_sec', 0):.2f}")
                print(f"  Latency: {metrics.get('time_per_req_mean', 0):.2f} ms")
                print(f"  Failed: {metrics.get('failed', 0)}")
            else:
                print(f"  ERROR: Failed to parse benchmark results")

        finally:
            # Stop server
            print(f"Stopping {name} server...")
            stop_server(proc)
            time.sleep(1)

    # Print final results
    if results:
        format_results(results)
    else:
        print("\nERROR: No benchmark results collected")
        sys.exit(1)


if __name__ == "__main__":
    main()
