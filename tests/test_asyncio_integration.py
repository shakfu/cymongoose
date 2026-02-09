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
