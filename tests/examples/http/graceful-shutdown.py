import signal

from cymongoose import MG_EV_HTTP_MSG, Manager

shutdown_requested = False


def signal_handler(sig, frame):
    global shutdown_requested
    shutdown_requested = True


def handler(conn, event, data):
    if event == MG_EV_HTTP_MSG:
        conn.reply(200, "Hello, World!")


signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)

mgr = Manager(handler)
mgr.listen("http://0.0.0.0:8000", http=True)

print("Server running on http://localhost:8000. Press Ctrl+C to stop.")
try:
    while not shutdown_requested:
        mgr.poll(100)  # 100ms for responsive shutdown
    print("Shutting down...")
finally:
    mgr.close()
    print("Server stopped cleanly")
