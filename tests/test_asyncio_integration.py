"""Tests for asyncio integration (AsyncManager)."""

import asyncio
import urllib.request

import pytest

from cymongoose import MG_EV_HTTP_MSG, MG_EV_WAKEUP, AsyncManager
from tests.conftest import get_free_port


@pytest.mark.asyncio
async def test_async_manager_lifecycle():
    """Test that AsyncManager starts and stops cleanly."""
    async with AsyncManager() as am:
        assert am.running
        assert am.manager is not None

    assert not am.running


@pytest.mark.asyncio
async def test_async_manager_http_server():
    """Test serving HTTP requests inside AsyncManager."""
    port = get_free_port()

    def handler(conn, ev, data):
        if ev == MG_EV_HTTP_MSG:
            conn.reply(200, b"hello from async")

    async with AsyncManager(handler, poll_interval=10) as am:
        am.listen(f"http://0.0.0.0:{port}", http=True)
        await asyncio.sleep(0.3)

        loop = asyncio.get_running_loop()
        response = await loop.run_in_executor(
            None,
            lambda: urllib.request.urlopen(
                f"http://127.0.0.1:{port}/",
                timeout=5,
            ),
        )
        body = response.read()
        assert body == b"hello from async"


@pytest.mark.asyncio
async def test_async_manager_schedule():
    """Test schedule() delivers events from mongoose thread to asyncio."""
    port = get_free_port()
    results = []
    event = asyncio.Event()

    def _record(value):
        results.append(value)
        event.set()

    def handler(conn, ev, data):
        if ev == MG_EV_HTTP_MSG:
            conn.reply(200, b"OK")
            am.schedule(lambda: _record("handler_fired"))

    async with AsyncManager(handler, poll_interval=10) as am:
        am.listen(f"http://0.0.0.0:{port}", http=True)
        await asyncio.sleep(0.3)

        loop = asyncio.get_running_loop()
        await loop.run_in_executor(
            None,
            lambda: urllib.request.urlopen(
                f"http://127.0.0.1:{port}/",
                timeout=5,
            ),
        )

        await asyncio.wait_for(event.wait(), timeout=5)

    assert results == ["handler_fired"]


@pytest.mark.asyncio
async def test_async_manager_schedule_coroutine():
    """Test schedule() with a coroutine (not just a plain callback)."""
    port = get_free_port()
    results = []
    event = asyncio.Event()

    async def on_request():
        results.append("coro_fired")
        event.set()

    def handler(conn, ev, data):
        if ev == MG_EV_HTTP_MSG:
            conn.reply(200, b"OK")
            am.schedule(on_request())

    async with AsyncManager(handler, poll_interval=10) as am:
        am.listen(f"http://0.0.0.0:{port}", http=True)
        await asyncio.sleep(0.3)

        loop = asyncio.get_running_loop()
        await loop.run_in_executor(
            None,
            lambda: urllib.request.urlopen(
                f"http://127.0.0.1:{port}/",
                timeout=5,
            ),
        )

        await asyncio.wait_for(event.wait(), timeout=5)

    assert results == ["coro_fired"]


@pytest.mark.asyncio
async def test_async_manager_wakeup():
    """Test wakeup() sending data from asyncio to mongoose handler."""
    port = get_free_port()
    wakeup_data = []
    event = asyncio.Event()

    def handler(conn, ev, data):
        if ev == MG_EV_WAKEUP:
            wakeup_data.append(data)
            am.schedule(lambda: event.set())

    async with AsyncManager(handler, poll_interval=10) as am:
        listener = am.listen(f"http://0.0.0.0:{port}", http=True)
        await asyncio.sleep(0.3)

        ok = am.wakeup(listener.id, b"ping")
        assert ok

        await asyncio.wait_for(event.wait(), timeout=5)

    assert len(wakeup_data) > 0
    assert wakeup_data[0] == b"ping"


@pytest.mark.asyncio
async def test_async_manager_multiple_cycles():
    """Test that AsyncManager can be started and stopped multiple times."""
    for _ in range(3):
        async with AsyncManager() as am:
            assert am.running
        assert not am.running


# -- "not started" guard tests -----------------------------------------------


@pytest.mark.asyncio
async def test_not_started_listen():
    am = AsyncManager()
    with pytest.raises(RuntimeError, match="not started"):
        am.listen("http://0.0.0.0:8080")


@pytest.mark.asyncio
async def test_not_started_connect():
    am = AsyncManager()
    with pytest.raises(RuntimeError, match="not started"):
        am.connect("http://127.0.0.1:8080")


@pytest.mark.asyncio
async def test_not_started_mqtt_connect():
    am = AsyncManager()
    with pytest.raises(RuntimeError, match="not started"):
        am.mqtt_connect("mqtt://127.0.0.1:1883")


@pytest.mark.asyncio
async def test_not_started_mqtt_listen():
    am = AsyncManager()
    with pytest.raises(RuntimeError, match="not started"):
        am.mqtt_listen("mqtt://0.0.0.0:1883")


@pytest.mark.asyncio
async def test_not_started_sntp_connect():
    am = AsyncManager()
    with pytest.raises(RuntimeError, match="not started"):
        am.sntp_connect("sntp://time.google.com")


@pytest.mark.asyncio
async def test_not_started_wakeup():
    am = AsyncManager()
    with pytest.raises(RuntimeError, match="not started"):
        am.wakeup(1)


@pytest.mark.asyncio
async def test_not_started_timer_add():
    am = AsyncManager()
    with pytest.raises(RuntimeError, match="not started"):
        am.timer_add(1000, lambda: None)


@pytest.mark.asyncio
async def test_not_started_schedule():
    am = AsyncManager()
    with pytest.raises(RuntimeError, match="not started"):
        am.schedule(lambda: None)


@pytest.mark.asyncio
async def test_not_started_manager_property():
    am = AsyncManager()
    with pytest.raises(RuntimeError, match="not started"):
        _ = am.manager


# -- delegated method tests --------------------------------------------------


@pytest.mark.asyncio
async def test_async_manager_connect():
    """Test connect() delegates to underlying Manager."""
    async with AsyncManager(poll_interval=10) as am:
        conn = am.connect("http://127.0.0.1:9999")
        assert conn is not None
        assert conn.id > 0


@pytest.mark.asyncio
async def test_async_manager_timer_add():
    """Test timer_add() delegates to underlying Manager."""
    results = []

    async with AsyncManager(poll_interval=10) as am:
        timer = am.timer_add(50, lambda: results.append("tick"))
        assert timer is not None
        await asyncio.sleep(0.2)

    assert len(results) >= 1


@pytest.mark.asyncio
async def test_async_manager_mqtt_listen():
    """Test mqtt_listen() delegates to underlying Manager."""
    port = get_free_port()
    async with AsyncManager(poll_interval=10) as am:
        conn = am.mqtt_listen(f"mqtt://0.0.0.0:{port}")
        assert conn is not None
        assert conn.id > 0


@pytest.mark.asyncio
async def test_async_manager_sntp_connect():
    """Test sntp_connect() delegates to underlying Manager."""
    async with AsyncManager(poll_interval=10) as am:
        conn = am.sntp_connect("sntp://time.google.com")
        assert conn is not None
        assert conn.id > 0


@pytest.mark.asyncio
async def test_async_manager_mqtt_connect():
    """Test mqtt_connect() delegates to underlying Manager."""
    async with AsyncManager(poll_interval=10) as am:
        conn = am.mqtt_connect("mqtt://127.0.0.1:9999")
        assert conn is not None
        assert conn.id > 0


@pytest.mark.asyncio
async def test_async_manager_reentrant_timer_from_handler():
    """Test that a handler can call timer_add without deadlocking.

    Regression test: with threading.Lock the poll thread holds the lock
    during poll(), so calling timer_add from a handler (same thread)
    would deadlock.  RLock allows reentrant acquisition.
    """
    port = get_free_port()
    inner_fired = []
    event = asyncio.Event()

    def handler(conn, ev, data):
        if ev == MG_EV_HTTP_MSG:
            conn.reply(200, b"OK")

            # This call happens inside poll(), on the poll thread.
            # With a non-reentrant Lock this would deadlock.
            def _inner():
                inner_fired.append(True)
                am.schedule(event.set)

            am.timer_add(10, _inner, run_now=True)

    async with AsyncManager(handler, poll_interval=10) as am:
        am.listen(f"http://0.0.0.0:{port}", http=True)
        await asyncio.sleep(0.3)

        loop = asyncio.get_running_loop()
        await loop.run_in_executor(
            None,
            lambda: urllib.request.urlopen(
                f"http://127.0.0.1:{port}/",
                timeout=5,
            ),
        )

        await asyncio.wait_for(event.wait(), timeout=5)

    assert len(inner_fired) >= 1


# -- shutdown regression tests -----------------------------------------------


class TestAsyncManagerShutdown:
    """AsyncManager must shut down cleanly even with a large poll_interval
    and no connections registered."""

    @pytest.mark.asyncio
    async def test_shutdown_no_listeners_large_poll_interval(self):
        """Start/stop AsyncManager with poll_interval=5000 and no listeners.

        Regression: __aexit__ raised RuntimeError because _wake_poll() was
        a no-op (no connections) and join(2) timed out before a 5-second
        poll could finish, leaving poll() active when close() was called.
        """
        async with AsyncManager(poll_interval=5000) as am:
            assert am.running
        assert not am.running

    @pytest.mark.asyncio
    async def test_shutdown_no_listeners_default_interval(self):
        """Baseline: default poll_interval should also shut down cleanly."""
        async with AsyncManager() as am:
            assert am.running
        assert not am.running

    @pytest.mark.asyncio
    async def test_shutdown_with_listener_large_poll_interval(self):
        """With a listener the wakeup path should still work."""
        port = get_free_port()
        async with AsyncManager(poll_interval=5000) as am:
            am.listen(f"http://0.0.0.0:{port}", http=True)
            assert am.running
        assert not am.running

    @pytest.mark.asyncio
    @pytest.mark.filterwarnings("ignore::RuntimeWarning")
    async def test_aexit_warns_when_poll_thread_stuck(self):
        """Issue #12: __aexit__ must warn (not crash) if the poll thread
        does not stop within the timeout.  Manager.close() must NOT be
        called while poll() is still active.
        """
        import time as _time

        def blocking_handler(conn, ev, data):
            if ev == MG_EV_HTTP_MSG:
                _time.sleep(30)

        am = AsyncManager(
            blocking_handler,
            poll_interval=100,
            shutdown_timeout=6,
        )
        with pytest.warns(RuntimeWarning, match="did not stop"):
            async with am:
                port = get_free_port()
                am.listen(f"http://0.0.0.0:{port}")
                import urllib.request

                try:
                    urllib.request.urlopen(f"http://127.0.0.1:{port}/", timeout=1)
                except Exception:
                    pass
                await asyncio.sleep(0.5)
        # Manager must NOT have been closed (thread is still alive)
        assert am._manager is not None
