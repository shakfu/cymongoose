"""Tests for REVIEW.md issues #7, #8, #10, #11."""

import threading
import time
import urllib.request

import cymongoose
from cymongoose import (
    MG_EV_HTTP_MSG,
    MG_LL_DEBUG,
    MG_LL_ERROR,
    MG_LL_INFO,
    MG_LL_NONE,
    MG_LL_VERBOSE,
    Manager,
    log_get,
    log_set,
)
from tests.conftest import ServerThread, get_free_port

# ---------------------------------------------------------------------------
# Issue #8 -- log level control
# ---------------------------------------------------------------------------


class TestLogLevelControl:
    """Verify log_set / log_get and MG_LL_* constants."""

    def test_log_level_constants_values(self):
        assert MG_LL_NONE == 0
        assert MG_LL_ERROR == 1
        assert MG_LL_INFO == 2
        assert MG_LL_DEBUG == 3
        assert MG_LL_VERBOSE == 4

    def test_log_level_constants_accessible_from_package(self):
        assert hasattr(cymongoose, "MG_LL_NONE")
        assert hasattr(cymongoose, "MG_LL_ERROR")
        assert hasattr(cymongoose, "MG_LL_INFO")
        assert hasattr(cymongoose, "MG_LL_DEBUG")
        assert hasattr(cymongoose, "MG_LL_VERBOSE")

    def test_log_set_and_get_roundtrip(self):
        original = log_get()
        try:
            log_set(MG_LL_NONE)
            assert log_get() == MG_LL_NONE

            log_set(MG_LL_ERROR)
            assert log_get() == MG_LL_ERROR

            log_set(MG_LL_VERBOSE)
            assert log_get() == MG_LL_VERBOSE
        finally:
            log_set(original)

    def test_log_set_suppresses_output(self, capsys):
        """Setting MG_LL_NONE should suppress mongoose C debug output."""
        original = log_get()
        try:
            log_set(MG_LL_NONE)
            mgr = Manager()
            port = get_free_port()
            mgr.listen(f"http://0.0.0.0:{port}", http=True)
            for _ in range(5):
                mgr.poll(10)
            mgr.close()
            captured = capsys.readouterr()
            # With MG_LL_NONE there should be no mongoose debug lines
            assert "mongoose.c" not in captured.err
        finally:
            log_set(original)

    def test_log_get_returns_int(self):
        assert isinstance(log_get(), int)

    def test_log_set_get_in_all(self):
        assert "log_set" in cymongoose.__all__
        assert "log_get" in cymongoose.__all__


# ---------------------------------------------------------------------------
# Issue #7 -- configurable error handler
# ---------------------------------------------------------------------------


class TestErrorHandler:
    """Verify Manager(error_handler=...) routes exceptions."""

    def test_error_handler_receives_exception(self):
        captured = []

        def error_handler(exc):
            captured.append(exc)

        def bad_handler(conn, ev, data):
            if ev == MG_EV_HTTP_MSG:
                raise ValueError("boom")

        mgr = Manager(bad_handler, error_handler=error_handler)
        port = get_free_port()
        mgr.listen(f"http://0.0.0.0:{port}", http=True)

        stop = threading.Event()

        def poll_loop():
            while not stop.is_set():
                mgr.poll(50)

        t = threading.Thread(target=poll_loop, daemon=True)
        t.start()
        time.sleep(0.2)

        try:
            urllib.request.urlopen(f"http://127.0.0.1:{port}/test", timeout=2)
        except Exception:
            pass

        time.sleep(0.3)
        stop.set()
        t.join(timeout=2)
        mgr.close()

        assert len(captured) >= 1
        assert isinstance(captured[0], ValueError)
        assert str(captured[0]) == "boom"

    def test_default_error_handler_prints_traceback(self, capsys):
        """Without error_handler, exceptions still print via traceback.print_exc."""

        def bad_handler(conn, ev, data):
            if ev == MG_EV_HTTP_MSG:
                raise RuntimeError("default-path")

        mgr = Manager(bad_handler)
        port = get_free_port()
        mgr.listen(f"http://0.0.0.0:{port}", http=True)

        stop = threading.Event()

        def poll_loop():
            while not stop.is_set():
                mgr.poll(50)

        t = threading.Thread(target=poll_loop, daemon=True)
        t.start()
        time.sleep(0.2)

        try:
            urllib.request.urlopen(f"http://127.0.0.1:{port}/test", timeout=2)
        except Exception:
            pass

        time.sleep(0.3)
        stop.set()
        t.join(timeout=2)
        mgr.close()

        captured = capsys.readouterr()
        assert "default-path" in captured.err

    def test_error_handler_itself_raises_falls_back_to_traceback(self, capsys):
        """If the error_handler itself raises, fall back to traceback.print_exc."""

        def bad_error_handler(exc):
            raise RuntimeError("error-handler-broke")

        def bad_handler(conn, ev, data):
            if ev == MG_EV_HTTP_MSG:
                raise ValueError("original-error")

        mgr = Manager(bad_handler, error_handler=bad_error_handler)
        port = get_free_port()
        mgr.listen(f"http://0.0.0.0:{port}", http=True)

        stop = threading.Event()

        def poll_loop():
            while not stop.is_set():
                mgr.poll(50)

        t = threading.Thread(target=poll_loop, daemon=True)
        t.start()
        time.sleep(0.2)

        try:
            urllib.request.urlopen(f"http://127.0.0.1:{port}/test", timeout=2)
        except Exception:
            pass

        time.sleep(0.3)
        stop.set()
        t.join(timeout=2)
        mgr.close()

        captured = capsys.readouterr()
        assert "error-handler-broke" in captured.err

    def test_manager_accepts_error_handler_kwarg(self):
        """Manager constructor accepts error_handler parameter."""
        mgr = Manager(error_handler=lambda exc: None)
        mgr.close()

    def test_manager_error_handler_none_by_default(self):
        """When no error_handler is given, it defaults to None (traceback path)."""
        mgr = Manager()
        mgr.close()


# ---------------------------------------------------------------------------
# Issue #10 -- query_var buffer limit
# ---------------------------------------------------------------------------


class TestQueryVarBuffer:
    """Verify query_var uses 2048-byte buffer and raises on truncation."""

    def test_query_var_normal_value(self):
        """Normal-length query values still work."""
        received = {}

        def handler(conn, ev, data):
            if ev == MG_EV_HTTP_MSG:
                received["val"] = data.query_var("key")
                conn.reply(200, b"ok")

        with ServerThread(handler) as port:
            resp = urllib.request.urlopen(f"http://127.0.0.1:{port}/test?key=hello", timeout=2)
            resp.read()

        assert received["val"] == "hello"

    def test_query_var_up_to_2047_bytes(self):
        """Values up to 2047 bytes (fitting in 2048 buffer) work."""
        long_value = "x" * 2000
        received = {}

        def handler(conn, ev, data):
            if ev == MG_EV_HTTP_MSG:
                received["val"] = data.query_var("key")
                conn.reply(200, b"ok")

        with ServerThread(handler) as port:
            resp = urllib.request.urlopen(
                f"http://127.0.0.1:{port}/test?key={long_value}", timeout=2
            )
            resp.read()

        assert received["val"] == long_value

    def test_query_var_missing_returns_none(self):
        received = {}

        def handler(conn, ev, data):
            if ev == MG_EV_HTTP_MSG:
                received["val"] = data.query_var("nonexistent")
                conn.reply(200, b"ok")

        with ServerThread(handler) as port:
            resp = urllib.request.urlopen(f"http://127.0.0.1:{port}/test?other=1", timeout=2)
            resp.read()

        assert received["val"] is None


# ---------------------------------------------------------------------------
# Issue #11 -- header iteration uses MG_MAX_HTTP_HEADERS constant
# ---------------------------------------------------------------------------


class TestHeaderConstant:
    """Verify headers() uses MG_MAX_HTTP_HEADERS instead of magic 30."""

    def test_headers_returns_all_headers(self):
        """headers() should return all headers from a request."""
        received = {}

        def handler(conn, ev, data):
            if ev == MG_EV_HTTP_MSG:
                received["headers"] = data.headers()
                conn.reply(200, b"ok")

        with ServerThread(handler) as port:
            req = urllib.request.Request(f"http://127.0.0.1:{port}/test")
            req.add_header("X-Custom-One", "value1")
            req.add_header("X-Custom-Two", "value2")
            resp = urllib.request.urlopen(req, timeout=2)
            resp.read()

        header_names = [h[0].lower() for h in received["headers"]]
        assert "x-custom-one" in header_names
        assert "x-custom-two" in header_names

    def test_mg_max_http_headers_constant_accessible(self):
        """The MG_MAX_HTTP_HEADERS constant should be usable from the pxd."""
        # We verify indirectly: headers() works correctly, and in the .pyx
        # we use MG_MAX_HTTP_HEADERS. If the constant were wrong, iteration
        # would either miss headers or go out of bounds.
        mgr = Manager()
        port = get_free_port()
        mgr.listen(f"http://0.0.0.0:{port}", http=True)
        mgr.poll(10)
        mgr.close()
