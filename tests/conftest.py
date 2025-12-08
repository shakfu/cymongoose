"""Shared pytest fixtures and utilities."""

import socket
import threading


def get_free_port():
    """Get a free TCP port by binding to port 0 and letting the OS choose."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.bind(("", 0))
    port = sock.getsockname()[1]
    sock.close()
    return port


class ServerThread:
    """Context manager for running a server in a background thread."""

    def __init__(self, handler, http=True):
        self.handler = handler
        self.http = http
        self.manager = None
        self.thread = None
        self.stop_flag = threading.Event()
        self.port = get_free_port()

    def __enter__(self):
        from cymongoose import Manager

        def run_server():
            self.manager = Manager(self.handler)
            self.manager.listen(f"http://0.0.0.0:{self.port}", http=self.http)
            while not self.stop_flag.is_set():
                self.manager.poll(100)

        self.thread = threading.Thread(target=run_server, daemon=True)
        self.thread.start()

        # Give server time to start
        import time

        time.sleep(0.3)

        return self.port

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.stop_flag.set()
        if self.thread:
            self.thread.join(timeout=2)
