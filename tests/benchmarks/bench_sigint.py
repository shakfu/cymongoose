#!/usr/bin/env python3
"""Test actual SIGINT handling."""

import signal
import os
import time
from cymongoose import Manager, MG_EV_HTTP_MSG


def handler(conn, ev, data):
    if ev == MG_EV_HTTP_MSG:
        conn.reply(200, b'{"ok":true}')


print("Testing SIGINT during poll()...")
manager = Manager(handler)
manager.listen("http://0.0.0.0:58345", http=True)
print("Server started, will send SIGINT in 0.5 seconds")

# Schedule SIGINT during poll
import threading


def send_signal():
    time.sleep(0.5)
    print("Sending SIGINT...")
    os.kill(os.getpid(), signal.SIGINT)


threading.Thread(target=send_signal, daemon=True).start()

try:
    print("Entering poll loop...")
    for i in range(100):
        manager.poll(100)
        if i == 0:
            print("  First poll completed")
    print("ERROR: Loop completed without interrupt!")
except KeyboardInterrupt:
    print("[x] KeyboardInterrupt caught successfully!")
finally:
    print("Cleaning up...")
    manager.close()
    print("[x] Cleanup complete")
