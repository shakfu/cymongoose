#!/usr/bin/env python3
"""Test signal handler pattern for Ctrl+C."""

import signal
import os
import time
import threading
from cymongoose import Manager, MG_EV_HTTP_MSG

shutdown_requested = False


def signal_handler(sig, frame):
    global shutdown_requested
    shutdown_requested = True
    print("[x] Signal handler called!")


def handler(conn, ev, data):
    if ev == MG_EV_HTTP_MSG:
        conn.reply(200, b'{"ok":true}')


print("Testing signal handler pattern...")
signal.signal(signal.SIGINT, signal_handler)

manager = Manager(handler)
manager.listen("http://0.0.0.0:58789", http=True)
print("Server started")


# Send SIGINT after 0.5 seconds
def send_signal():
    time.sleep(0.5)
    print("Sending SIGINT...")
    os.kill(os.getpid(), signal.SIGINT)


threading.Thread(target=send_signal, daemon=True).start()

try:
    polls = 0
    while not shutdown_requested and polls < 20:
        manager.poll(100)
        polls += 1
        if polls == 1:
            print("  First poll completed")

    if shutdown_requested:
        print("[x] Shutdown flag set correctly!")
    else:
        print("[X] Shutdown flag NOT set")

finally:
    manager.close()
    print("[x] Cleanup complete")

print(f"\n{'[x] TEST PASSED' if shutdown_requested else '[X] TEST FAILED'}")
