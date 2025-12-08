#!/usr/bin/env python3
"""Direct test without subprocess."""

import time
import threading
import socket
import urllib.request

from cymongoose import Manager, MG_EV_HTTP_MSG


def get_free_port():
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.bind(("", 0))
    port = sock.getsockname()[1]
    sock.close()
    return port


port = get_free_port()
json_response = b'{"message":"Hello, World!"}'
stop_flag = threading.Event()


def handler(conn, ev, data):
    print(f"Handler called: ev={ev}, MG_EV_HTTP_MSG={MG_EV_HTTP_MSG}", flush=True)
    if ev == MG_EV_HTTP_MSG:
        print("Sending reply...", flush=True)
        conn.reply(200, json_response, headers={"Content-Type": "application/json"})


def run_server():
    manager = Manager(handler)
    manager.listen(f"http://0.0.0.0:{port}", http=True)
    print(f"Server listening on port {port}", flush=True)
    while not stop_flag.is_set():
        manager.poll(100)


server_thread = threading.Thread(target=run_server, daemon=True)
server_thread.start()
time.sleep(1)

print(f"\nTesting with urllib on port {port}...")
try:
    response = urllib.request.urlopen(f"http://localhost:{port}/", timeout=5)
    body = response.read()
    print(f"Success! Status: {response.status}, Body: {body}")
except Exception as e:
    print(f"Error: {e}")

stop_flag.set()
time.sleep(0.2)
print("Done")
