"""Shared pytest fixtures and utilities."""

import socket
import threading


def get_free_port():
    """Get a free TCP port by binding to port 0 and letting the OS choose."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.bind(("127.0.0.1", 0))
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
        self.ready = threading.Event()
        self.port = get_free_port()

    def __enter__(self):
        from cymongoose import Manager

        def run_server():
            self.manager = Manager(self.handler)
            self.manager.listen(f"http://0.0.0.0:{self.port}", http=self.http)
            self.ready.set()
            while not self.stop_flag.is_set():
                self.manager.poll(100)

        self.thread = threading.Thread(target=run_server, daemon=True)
        self.thread.start()

        # 15s, not 5: the wait covers thread start plus Manager() and listen(),
        # none of which the tests are measuring. A loaded machine (a rebuild
        # still settling, Windows CI at 2.6x Linux runtime) overran 5s and
        # failed an unrelated test. Still under the 60s pytest timeout.
        if not self.ready.wait(timeout=15):
            raise RuntimeError("Server failed to start within 15 seconds")

        return self.port

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.stop_flag.set()
        if self.thread:
            self.thread.join(timeout=2)
        if self.manager:
            self.manager.close()
