"""Asyncio-compatible wrapper around the cymongoose Manager.

Runs the mongoose event loop in a daemon thread.  ``poll()`` releases
the GIL, so the asyncio event loop runs concurrently without blocking.
The thread-safe ``wakeup()`` method enables asyncio -> mongoose
communication.
"""

from __future__ import annotations

import asyncio
import threading
from typing import Any, Callable, Optional

from ._mongoose import Connection, Manager, Timer


class AsyncManager:
    """Asyncio-compatible wrapper around Manager.

    Runs the mongoose event loop in a daemon thread.  ``poll()`` releases
    the GIL, so the asyncio event loop runs concurrently without blocking.
    The thread-safe ``wakeup()`` method enables asyncio -> mongoose
    communication.

    Usage::

        async with AsyncManager(handler) as am:
            am.listen("http://0.0.0.0:8080")
            # ... do async work ...
    """

    def __init__(
        self,
        handler: Optional[Callable[..., Any]] = None,
        poll_interval: int = 100,
        error_handler: Optional[Callable[[Exception], Any]] = None,
    ) -> None:
        self._handler = handler
        self._poll_interval = poll_interval
        self._error_handler = error_handler
        self._manager: Optional[Manager] = None
        self._thread: Optional[threading.Thread] = None
        self._stop = threading.Event()
        self._lock = threading.RLock()
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._wake_id: int = 0  # connection ID used to interrupt poll()

    # -- async context manager -----------------------------------------------

    async def __aenter__(self) -> "AsyncManager":
        self._loop = asyncio.get_running_loop()
        self._manager = Manager(
            self._handler,
            enable_wakeup=True,
            error_handler=self._error_handler,
        )
        self._stop.clear()
        self._wake_id = 0
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()
        return self

    async def __aexit__(self, *exc: Any) -> None:
        self._stop.set()
        # Interrupt poll() so the thread exits promptly
        self._wake_poll()
        if self._thread is not None:
            await asyncio.get_running_loop().run_in_executor(
                None,
                self._thread.join,
                2,
            )
            self._thread = None
        if self._manager is not None:
            self._manager.close()
            self._manager = None
        self._loop = None

    # -- poll loop (runs in background thread) -------------------------------

    def _run(self) -> None:
        while not self._stop.is_set():
            with self._lock:
                if self._manager is not None:
                    self._manager.poll(self._poll_interval)

    # -- internal helpers ----------------------------------------------------

    def _wake_poll(self) -> None:
        """Best-effort interrupt of poll() to reduce lock acquisition latency.

        Writes to the wakeup pipe so ``select()``/``epoll_wait()`` returns
        immediately, causing ``poll()`` to release the lock sooner.
        """
        if self._wake_id > 0 and self._manager is not None:
            try:
                self._manager.wakeup(self._wake_id, b"")
            except Exception:
                pass  # manager may be closing

    def _track_conn(self, conn: Connection) -> None:
        """Remember a connection ID for future _wake_poll() calls."""
        if self._wake_id == 0 and conn.id > 0:
            self._wake_id = conn.id

    # -- delegated methods ---------------------------------------------------

    def listen(
        self,
        url: str,
        handler: Optional[Callable[..., Any]] = None,
        *,
        http: Optional[bool] = None,
    ) -> Connection:
        if self._manager is None:
            raise RuntimeError("AsyncManager is not started")
        self._wake_poll()
        with self._lock:
            conn = self._manager.listen(url, handler=handler, http=http)
        self._track_conn(conn)
        return conn

    def connect(
        self,
        url: str,
        handler: Optional[Callable[..., Any]] = None,
        *,
        http: Optional[bool] = None,
    ) -> Connection:
        if self._manager is None:
            raise RuntimeError("AsyncManager is not started")
        self._wake_poll()
        with self._lock:
            conn = self._manager.connect(url, handler=handler, http=http)
        self._track_conn(conn)
        return conn

    def mqtt_connect(self, url: str, **kwargs: Any) -> Connection:
        if self._manager is None:
            raise RuntimeError("AsyncManager is not started")
        self._wake_poll()
        with self._lock:
            conn = self._manager.mqtt_connect(url, **kwargs)
        self._track_conn(conn)
        return conn

    def mqtt_listen(
        self,
        url: str,
        handler: Optional[Callable[..., Any]] = None,
    ) -> Connection:
        if self._manager is None:
            raise RuntimeError("AsyncManager is not started")
        self._wake_poll()
        with self._lock:
            conn = self._manager.mqtt_listen(url, handler=handler)
        self._track_conn(conn)
        return conn

    def sntp_connect(
        self,
        url: str,
        handler: Optional[Callable[..., Any]] = None,
    ) -> Connection:
        if self._manager is None:
            raise RuntimeError("AsyncManager is not started")
        self._wake_poll()
        with self._lock:
            conn = self._manager.sntp_connect(url, handler=handler)
        self._track_conn(conn)
        return conn

    def wakeup(self, connection_id: int, data: bytes = b"") -> bool:
        """Thread-safe: wakeup does not need the lock."""
        if self._manager is None:
            raise RuntimeError("AsyncManager is not started")
        return self._manager.wakeup(connection_id, data)

    def timer_add(
        self,
        ms: int,
        callback: Callable[..., Any],
        *,
        repeat: bool = False,
        run_now: bool = False,
    ) -> Timer:
        if self._manager is None:
            raise RuntimeError("AsyncManager is not started")
        self._wake_poll()
        with self._lock:
            return self._manager.timer_add(
                ms,
                callback,
                repeat=repeat,
                run_now=run_now,
            )

    # -- asyncio helper ------------------------------------------------------

    def schedule(self, coro_or_callback: Any) -> None:
        """Schedule a coroutine or callback on the asyncio event loop.

        This is thread-safe and intended to be called from the mongoose
        poll thread (i.e. from inside event handlers) to push work back
        onto the asyncio loop.
        """
        if self._loop is None:
            raise RuntimeError("AsyncManager is not started")
        if asyncio.iscoroutine(coro_or_callback):
            asyncio.run_coroutine_threadsafe(coro_or_callback, self._loop)
        else:
            self._loop.call_soon_threadsafe(coro_or_callback)

    # -- properties ----------------------------------------------------------

    @property
    def manager(self) -> Manager:
        """Access the underlying Manager."""
        if self._manager is None:
            raise RuntimeError("AsyncManager is not started")
        return self._manager

    @property
    def running(self) -> bool:
        return self._thread is not None and self._thread.is_alive() and not self._stop.is_set()
