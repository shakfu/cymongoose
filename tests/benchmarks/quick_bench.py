#!/usr/bin/env python3
"""
Quick benchmark using sequential requests (reliable on all platforms).
For proper load testing, use wrk: brew install wrk
"""

import socket
import threading
import time
import urllib.request

from cymongoose import MG_EV_HTTP_MSG, Manager


def get_free_port():
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.bind(("", 0))
    port = sock.getsockname()[1]
    sock.close()
    return port


def main():
    print(" cymongoose Quick Benchmark")
    print("=" * 60)

    # Start server
    port = get_free_port()
    json_response = b'{"message":"Hello, World!"}'
    stop_flag = threading.Event()

    def handler(conn, ev, data):
        if ev == MG_EV_HTTP_MSG:
            conn.reply(200, json_response, headers={"Content-Type": "application/json"})

    def run_server():
        manager = Manager(handler)
        manager.listen(f"http://0.0.0.0:{port}", http=True)
        while not stop_flag.is_set():
            manager.poll(100)

    server_thread = threading.Thread(target=run_server, daemon=True)
    server_thread.start()
    time.sleep(0.5)

    url = f"http://localhost:{port}/"

    # Warmup
    print("Warming up...")
    for _ in range(10):
        urllib.request.urlopen(url, timeout=5).read()

    # Benchmark: Sequential requests (reliable measurement)
    print("\nRunning benchmark (1000 sequential requests)...")
    start_time = time.time()
    successful = 0
    latencies = []

    for i in range(1000):
        try:
            req_start = time.time()
            response = urllib.request.urlopen(url, timeout=5)
            response.read()
            latency = (time.time() - req_start) * 1000  # ms
            latencies.append(latency)
            successful += 1

            if (i + 1) % 100 == 0:
                print(f"  Progress: {i + 1}/1000")
        except Exception as e:
            print(f"  Request {i + 1} failed: {e}")

    total_time = time.time() - start_time

    # Calculate stats
    avg_latency = sum(latencies) / len(latencies) if latencies else 0
    min_latency = min(latencies) if latencies else 0
    max_latency = max(latencies) if latencies else 0
    requests_per_sec = successful / total_time if total_time > 0 else 0

    # Results
    print("\n" + "=" * 60)
    print("RESULTS (Sequential Requests)")
    print("=" * 60)
    print(f"Total requests:    {successful}")
    print(f"Total time:        {total_time:.2f} seconds")
    print(f"Requests/second:   {requests_per_sec:.2f}")
    print(f"Average latency:   {avg_latency:.2f} ms")
    print(f"Min latency:       {min_latency:.2f} ms")
    print(f"Max latency:       {max_latency:.2f} ms")
    print("=" * 60)

    print("\n For concurrent load testing, use wrk:")
    print("   1. Start server: uv run python benchmarks/demo_server.py")
    print("   2. Install wrk:  brew install wrk")
    print("   3. Run test:     wrk -t4 -c100 -d10s http://localhost:8765/")
    print("\n   See benchmarks/MANUAL_BENCHMARK.md for details")

    # Cleanup
    stop_flag.set()
    time.sleep(0.2)


if __name__ == "__main__":
    main()
