#!/usr/bin/env python3
"""Test cleanup and shutdown behavior."""

import signal
import time

from cymongoose import MG_EV_HTTP_MSG, Manager

shutdown = False


def signal_handler(sig, frame):
    global shutdown
    shutdown = True
    print("\nSIGINT received, shutting down...")


def handler(conn, ev, data):
    if ev == MG_EV_HTTP_MSG:
        conn.reply(200, b'{"ok":true}')


print("Testing cymongoose cleanup...")
print("Server will auto-shutdown in 2 seconds")

signal.signal(signal.SIGINT, signal_handler)

manager = Manager(handler)
manager.listen("http://0.0.0.0:58234", http=True)
print("Server listening on port 58234")

# Auto-shutdown after 2 seconds for testing
start_time = time.time()

try:
    while not shutdown and (time.time() - start_time) < 2:
        manager.poll(100)

    if not shutdown:
        print("\nAuto-shutdown after 2 seconds")

except KeyboardInterrupt:
    print("\nKeyboardInterrupt caught!")

finally:
    print("Calling manager.close()...")
    manager.close()
    print("[x] Cleanup complete - Manager closed successfully")

print("\nTest passed! Cleanup works correctly.")
