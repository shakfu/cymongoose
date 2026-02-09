"""Tests for Manager.run() convenience method."""

import os
import signal

import pytest

from cymongoose import Manager, MG_EV_HTTP_MSG


def _is_closed(mgr):
    """Check if a manager has been closed by attempting to poll it."""
    try:
        mgr.poll(0)
        return False
    except RuntimeError:
        return True


def test_run_exits_on_sigint():
    """run() should exit cleanly when SIGINT is received."""
    mgr = Manager()

    def send_signal():
        os.kill(os.getpid(), signal.SIGINT)

    mgr.timer_add(200, send_signal)
    mgr.run()
    # run() calls close(), so poll should raise
    assert _is_closed(mgr)


def test_run_exits_on_sigterm():
    """run() should exit cleanly when SIGTERM is received."""
    mgr = Manager()

    def send_signal():
        os.kill(os.getpid(), signal.SIGTERM)

    mgr.timer_add(200, send_signal)
    mgr.run()
    assert _is_closed(mgr)


def test_run_calls_close():
    """run() should call close() after exiting the poll loop."""
    mgr = Manager()

    def send_signal():
        os.kill(os.getpid(), signal.SIGINT)

    mgr.timer_add(200, send_signal)
    mgr.run()
    assert _is_closed(mgr)
    # Calling close() again should be safe (idempotent)
    mgr.close()


def test_run_restores_signal_handlers():
    """run() should restore original signal handlers after returning."""
    original_int = signal.getsignal(signal.SIGINT)
    original_term = signal.getsignal(signal.SIGTERM)

    mgr = Manager()

    def send_signal():
        os.kill(os.getpid(), signal.SIGINT)

    mgr.timer_add(200, send_signal)
    mgr.run()

    assert signal.getsignal(signal.SIGINT) is original_int
    assert signal.getsignal(signal.SIGTERM) is original_term


def test_run_custom_poll_ms():
    """run() should accept a custom poll_ms argument."""
    mgr = Manager()

    def send_signal():
        os.kill(os.getpid(), signal.SIGINT)

    mgr.timer_add(200, send_signal)
    mgr.run(poll_ms=50)
    assert _is_closed(mgr)


def test_run_processes_events():
    """run() should process events while the loop is running."""
    mgr = Manager()
    mgr.listen("http://0.0.0.0:0", http=True)

    def send_signal():
        os.kill(os.getpid(), signal.SIGINT)

    mgr.timer_add(200, send_signal)
    mgr.run()
    assert _is_closed(mgr)
