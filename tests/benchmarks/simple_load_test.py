#!/usr/bin/env python3
"""Simple load test without ab dependency."""

import time
import threading
import socket
import urllib.request
import urllib.error
from concurrent.futures import ThreadPoolExecutor, as_completed

from cymongoose import Manager, MG_EV_HTTP_MSG


def get_free_port():
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.bind(("", 0))
    port = sock.getsockname()[1]
    sock.close()
    return port


def make_request(url):
    """Make a single HTTP request and return (success, duration)."""
    start = time.time()
    try:
        response = urllib.request.urlopen(url, timeout=5)
        response.read()
        duration = time.time() - start
        return (True, duration, response.status)
    except Exception as e:
        duration = time.time() - start
        return (False, duration, str(e))


def run_load_test(url, num_requests=1000, concurrency=10):
    """Run concurrent load test."""
    print(f"Load test: {num_requests} requests, {concurrency} concurrent")

    results = []
    start_time = time.time()

    with ThreadPoolExecutor(max_workers=concurrency) as executor:
        futures = [executor.submit(make_request, url) for _ in range(num_requests)]

        for i, future in enumerate(as_completed(futures), 1):
            result = future.result()
            results.append(result)

            if i % 100 == 0:
                print(f"  Completed: {i}/{num_requests}")

    total_time = time.time() - start_time

    # Calculate stats
    successful = sum(1 for r in results if r[0])
    failed = len(results) - successful
    durations = [r[1] for r in results if r[0]]

    if durations:
        avg_latency = sum(durations) / len(durations) * 1000  # ms
        min_latency = min(durations) * 1000
        max_latency = max(durations) * 1000
        requests_per_sec = num_requests / total_time
    else:
        avg_latency = min_latency = max_latency = requests_per_sec = 0

    print("\n" + "=" * 60)
    print("RESULTS")
    print("=" * 60)
    print(f"Total time:        {total_time:.2f} seconds")
    print(f"Requests/second:   {requests_per_sec:.2f}")
    print(f"Successful:        {successful}")
    print(f"Failed:            {failed}")
    print(f"Average latency:   {avg_latency:.2f} ms")
    print(f"Min latency:       {min_latency:.2f} ms")
    print(f"Max latency:       {max_latency:.2f} ms")
    print("=" * 60)


def main():
    print("Starting cymongoose server...")

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

    print(f"Server running on port {port}\n")

    # Test connection
    url = f"http://localhost:{port}/"
    try:
        response = urllib.request.urlopen(url, timeout=5)
        print(f"Server check: {response.status} OK\n")
    except Exception as e:
        print(f"ERROR: Server not responding: {e}")
        return

    # Run load test
    run_load_test(url, num_requests=5000, concurrency=50)

    # Cleanup
    print("\nStopping server...")
    stop_flag.set()
    time.sleep(0.2)
    print("Done")


if __name__ == "__main__":
    main()
