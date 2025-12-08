"""Tests for Timer API."""

import pytest
import time
import threading
from cymongoose import Manager


def test_timer_single_shot():
    """Test single-shot timer fires once."""
    manager = Manager()
    call_count = [0]

    def timer_callback():
        call_count[0] += 1

    try:
        timer = manager.timer_add(50, timer_callback, repeat=False)
        assert timer is not None

        # Poll for timer to fire
        for _ in range(10):
            manager.poll(10)
            time.sleep(0.01)

        # Should have fired once
        assert call_count[0] == 1

        # Wait longer, should not fire again
        for _ in range(10):
            manager.poll(10)
            time.sleep(0.01)

        assert call_count[0] == 1  # Still 1
    finally:
        manager.close()


def test_timer_repeating():
    """Test repeating timer fires multiple times."""
    manager = Manager()
    call_count = [0]

    def timer_callback():
        call_count[0] += 1

    try:
        timer = manager.timer_add(30, timer_callback, repeat=True)
        assert timer is not None

        # Poll for timer to fire multiple times
        for _ in range(30):
            manager.poll(10)
            time.sleep(0.01)

        # Should have fired multiple times
        assert call_count[0] >= 3
    finally:
        manager.close()


def test_timer_run_now():
    """Test timer with run_now flag fires immediately."""
    manager = Manager()
    call_count = [0]

    def timer_callback():
        call_count[0] += 1

    try:
        timer = manager.timer_add(1000, timer_callback, run_now=True, repeat=False)
        assert timer is not None

        # Poll once - should fire immediately
        manager.poll(10)

        assert call_count[0] == 1
    finally:
        manager.close()


def test_timer_exception_in_callback():
    """Test that exceptions in timer callback don't crash."""
    manager = Manager()
    call_count = [0]

    def bad_callback():
        call_count[0] += 1
        raise RuntimeError("Timer callback error")

    try:
        timer = manager.timer_add(50, bad_callback, repeat=True)

        # Poll - should handle exception gracefully
        for _ in range(10):
            manager.poll(10)
            time.sleep(0.01)

        # Timer should still have fired despite exceptions
        assert call_count[0] >= 1
    finally:
        manager.close()


def test_multiple_timers():
    """Test multiple timers can coexist."""
    manager = Manager()
    call_counts = {"timer1": 0, "timer2": 0, "timer3": 0}

    def make_callback(name):
        def callback():
            call_counts[name] += 1

        return callback

    try:
        timer1 = manager.timer_add(30, make_callback("timer1"), repeat=True)
        timer2 = manager.timer_add(50, make_callback("timer2"), repeat=True)
        timer3 = manager.timer_add(100, make_callback("timer3"), repeat=False)

        # Poll for timers to fire
        for _ in range(50):
            manager.poll(10)
            time.sleep(0.01)

        # All timers should have fired
        assert call_counts["timer1"] >= 2
        assert call_counts["timer2"] >= 1
        assert call_counts["timer3"] == 1  # Single shot
    finally:
        manager.close()


def test_timer_cleanup_on_manager_close():
    """Test that timers are cleaned up when manager is closed."""
    manager = Manager()
    call_count = [0]

    def timer_callback():
        call_count[0] += 1

    timer = manager.timer_add(50, timer_callback, repeat=True)

    # Poll a few times
    for _ in range(5):
        manager.poll(10)
        time.sleep(0.01)

    initial_count = call_count[0]

    # Close manager
    manager.close()

    # Sleep - timer should not fire after close
    time.sleep(0.2)

    # Count should not increase
    assert call_count[0] == initial_count


def test_timer_with_background_polling():
    """Test timer with background polling thread."""
    manager = Manager()
    call_count = [0]
    stop_flag = threading.Event()

    def timer_callback():
        call_count[0] += 1

    def poll_thread():
        while not stop_flag.is_set():
            manager.poll(50)

    try:
        timer = manager.timer_add(40, timer_callback, repeat=True)

        thread = threading.Thread(target=poll_thread)
        thread.start()

        # Let timer fire multiple times
        time.sleep(0.3)

        assert call_count[0] >= 3
    finally:
        stop_flag.set()
        thread.join(timeout=1)
        manager.close()


def test_timer_autodelete():
    """Test that single-shot timers auto-delete after firing."""
    manager = Manager()
    call_count = [0]

    def timer_callback():
        call_count[0] += 1

    try:
        # Create single-shot timer (autodelete enabled by default)
        timer = manager.timer_add(50, timer_callback, repeat=False)

        # Poll until it fires
        for _ in range(15):
            manager.poll(10)
            time.sleep(0.01)

        assert call_count[0] == 1

        # Timer should be auto-deleted, further polls shouldn't fire it
        for _ in range(20):
            manager.poll(10)
            time.sleep(0.01)

        assert call_count[0] == 1  # Still 1, didn't fire again
    finally:
        manager.close()


def test_timer_zero_milliseconds():
    """Test timer with zero milliseconds fires on next poll."""
    manager = Manager()
    call_count = [0]

    def timer_callback():
        call_count[0] += 1

    try:
        timer = manager.timer_add(0, timer_callback, repeat=False)

        # Should fire on next poll
        manager.poll(10)

        assert call_count[0] == 1
    finally:
        manager.close()


def test_timer_method_exists():
    """Test that timer methods exist and are callable."""
    manager = Manager()

    try:
        # Manager should have timer_add
        assert hasattr(manager, "timer_add")
        assert callable(manager.timer_add)

        # Should create timer without error
        timer = manager.timer_add(1000, lambda: None)
        assert timer is not None
    finally:
        manager.close()
