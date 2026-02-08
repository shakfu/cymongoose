"""Asyncio-compatible wrapper around the cymongoose Manager.

Runs the mongoose event loop in a daemon thread.  ``poll()`` releases
the GIL, so the asyncio event loop runs concurrently without blocking.
The thread-safe ``wakeup()`` method enables asyncio -> mongoose
communication.
"""

from __future__ import annotations

import asyncio
import threading
from typing import Any, Callable, Optional, Union

from ._mongoose import Manager, Connection, Timer


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
        handler: Optional[Callable] = None,
        poll_interval: int = 100,
        error_handler: Optional[Callable[[Exception], Any]] = None,
    ) -> None:
        self._handler = handler
        self._poll_interval = poll_interval
        self._error_handler = error_handler
        self._manager: Optional[Manager] = None
        self._thread: Optional[threading.Thread] = None
        self._stop = threading.Event()
        self._lock = threading.Lock()
        self._loop: Optional[asyncio.AbstractEventLoop] = None

    # -- async context manager -----------------------------------------------

    async def __aenter__(self) -> "AsyncManager":
        self._loop = asyncio.get_running_loop()
        self._manager = Manager(
            self._handler, enable_wakeup=True, error_handler=self._error_handler,
        )
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()
        return self

    async def __aexit__(self, *exc: Any) -> None:
        self._stop.set()
        if self._thread is not None:
            await asyncio.get_running_loop().run_in_executor(
                None, self._thread.join, 2,
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

    # -- delegated methods ---------------------------------------------------

    def listen(
        self,
        url: str,
        handler: Optional[Callable] = None,
        *,
        http: bool = False,
    ) -> Connection:
        assert self._manager is not None, "AsyncManager is not started"
        with self._lock:
            return self._manager.listen(url, handler=handler, http=http)

    def connect(
        self,
        url: str,
        handler: Optional[Callable] = None,
        *,
        http: bool = False,
    ) -> Connection:
        assert self._manager is not None, "AsyncManager is not started"
        with self._lock:
            return self._manager.connect(url, handler=handler, http=http)

    def mqtt_connect(self, url: str, **kwargs: Any) -> Connection:
        assert self._manager is not None, "AsyncManager is not started"
        with self._lock:
            return self._manager.mqtt_connect(url, **kwargs)

    def mqtt_listen(
        self,
        url: str,
        handler: Optional[Callable] = None,
    ) -> Connection:
        assert self._manager is not None, "AsyncManager is not started"
        with self._lock:
            return self._manager.mqtt_listen(url, handler=handler)

    def sntp_connect(
        self,
        url: str,
        handler: Optional[Callable] = None,
    ) -> Connection:
        assert self._manager is not None, "AsyncManager is not started"
        with self._lock:
            return self._manager.sntp_connect(url, handler=handler)

    def wakeup(self, connection_id: int, data: bytes = b"") -> bool:
        """Thread-safe: wakeup does not need the lock."""
        assert self._manager is not None, "AsyncManager is not started"
        return self._manager.wakeup(connection_id, data)

    def timer_add(
        self,
        ms: int,
        callback: Callable,
        *,
        repeat: bool = False,
        run_now: bool = False,
    ) -> Timer:
        assert self._manager is not None, "AsyncManager is not started"
        with self._lock:
            return self._manager.timer_add(
                ms, callback, repeat=repeat, run_now=run_now,
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
        assert self._manager is not None, "AsyncManager is not started"
        return self._manager

    @property
    def running(self) -> bool:
        return (
            self._thread is not None
            and self._thread.is_alive()
            and not self._stop.is_set()
        )
