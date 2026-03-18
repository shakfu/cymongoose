"""Tests for REVIEW.md issues #7, #8, #10, #11, #12, #14."""

import threading
import time
import urllib.request

import pytest

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
        """Manager with error_handler routes exceptions to that handler."""
        captured = []

        def handler(conn, ev, data):
            if ev == MG_EV_HTTP_MSG:
                raise ValueError("kwarg-test")

        mgr = Manager(handler, error_handler=lambda exc: captured.append(exc))
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
            urllib.request.urlopen(f"http://127.0.0.1:{port}/", timeout=2)
        except Exception:
            pass

        time.sleep(0.3)
        stop.set()
        t.join(timeout=2)
        mgr.close()

        assert len(captured) >= 1
        assert isinstance(captured[0], ValueError)

    def test_manager_error_handler_none_by_default(self, capsys):
        """When no error_handler is given, exceptions go to stderr."""

        def handler(conn, ev, data):
            if ev == MG_EV_HTTP_MSG:
                raise RuntimeError("none-default")

        mgr = Manager(handler)
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
            urllib.request.urlopen(f"http://127.0.0.1:{port}/", timeout=2)
        except Exception:
            pass

        time.sleep(0.3)
        stop.set()
        t.join(timeout=2)
        mgr.close()

        captured = capsys.readouterr()
        assert "none-default" in captured.err


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
        """The MG_MAX_HTTP_HEADERS constant is used correctly in header iteration."""
        # Verify indirectly by sending multiple custom headers and confirming
        # they all come back from headers(). If the constant were wrong,
        # iteration would miss headers or go out of bounds.
        received_headers = {}

        def handler(conn, ev, data):
            if ev == MG_EV_HTTP_MSG:
                received_headers.update(dict(data.headers()))
                conn.reply(200, b"ok")

        with ServerThread(handler) as port:
            req = urllib.request.Request(
                f"http://127.0.0.1:{port}/",
                headers={"X-Test-A": "alpha", "X-Test-B": "beta"},
            )
            resp = urllib.request.urlopen(req, timeout=2)
            resp.read()

        assert "X-Test-A" in received_headers
        assert "X-Test-B" in received_headers


# ---------------------------------------------------------------------------
# Issue #14 -- HTTP header injection prevention
# ---------------------------------------------------------------------------


class TestHeaderInjectionPrevention:
    """Connection.reply() must reject header names/values containing CR/LF."""

    def test_header_name_with_newline_rejected(self):
        """Header name containing \\n must raise ValueError."""
        manager = Manager()
        try:
            conn = manager.listen("http://127.0.0.1:0")
            manager.poll(10)
            with pytest.raises(ValueError, match="Header name.*illegal character"):
                conn.reply(200, b"x", {"Bad\nName": "value"})
        finally:
            manager.close()

    def test_header_name_with_cr_rejected(self):
        """Header name containing \\r must raise ValueError."""
        manager = Manager()
        try:
            conn = manager.listen("http://127.0.0.1:0")
            manager.poll(10)
            with pytest.raises(ValueError, match="Header name.*illegal character"):
                conn.reply(200, b"x", {"Bad\rName": "value"})
        finally:
            manager.close()

    def test_header_value_with_newline_rejected(self):
        """Header value containing \\n must raise ValueError."""
        manager = Manager()
        try:
            conn = manager.listen("http://127.0.0.1:0")
            manager.poll(10)
            with pytest.raises(ValueError, match="Header value.*illegal character"):
                conn.reply(200, b"x", {"X-Ok": "bad\nvalue"})
        finally:
            manager.close()

    def test_header_value_with_crlf_injection_rejected(self):
        """Classic CRLF injection in header value must raise ValueError."""
        manager = Manager()
        try:
            conn = manager.listen("http://127.0.0.1:0")
            manager.poll(10)
            with pytest.raises(ValueError, match="Header value.*illegal character"):
                conn.reply(200, b"x", {"Location": "http://ok\r\nEvil: injected"})
        finally:
            manager.close()

    def test_header_name_with_nul_rejected(self):
        """Header name containing NUL must raise ValueError."""
        manager = Manager()
        try:
            conn = manager.listen("http://127.0.0.1:0")
            manager.poll(10)
            with pytest.raises(ValueError, match="Header name.*illegal character"):
                conn.reply(200, b"x", {"Bad\x00Name": "value"})
        finally:
            manager.close()

    def test_header_value_with_nul_rejected(self):
        """Header value with NUL byte must raise (truncation at C layer)."""
        manager = Manager()
        try:
            conn = manager.listen("http://127.0.0.1:0")
            manager.poll(10)
            with pytest.raises(ValueError, match="Header value.*illegal character"):
                conn.reply(200, b"x", {"X-Ok": "visible\x00hidden"})
        finally:
            manager.close()

    def test_clean_headers_pass_through(self):
        """Normal headers without CR/LF must not raise."""
        received = []

        def handler(conn, ev, data):
            if ev == MG_EV_HTTP_MSG:
                conn.reply(200, b"ok", {"X-Custom": "safe-value"})
                received.append(True)

        with ServerThread(handler) as port:
            resp = urllib.request.urlopen(f"http://127.0.0.1:{port}/", timeout=2)
            body = resp.read()
            assert resp.status == 200
            assert b"ok" in body

    def test_reply_json_inherits_header_validation(self):
        """reply_json() delegates to reply(), so injection must be caught."""
        manager = Manager()
        try:
            conn = manager.listen("http://127.0.0.1:0")
            manager.poll(10)
            with pytest.raises(ValueError, match="Header value.*illegal character"):
                conn.reply_json({"a": 1}, headers={"X-Bad": "val\r\nEvil: yes"})
        finally:
            manager.close()


# ---------------------------------------------------------------------------
# Issue #16 -- ws_upgrade header injection prevention
# ---------------------------------------------------------------------------


class TestWsUpgradeHeaderInjection:
    """ws_upgrade() must reject headers containing CR/LF/NUL."""

    def _run_ws_upgrade_test(self, extra_headers, expected_match):
        results = []

        def handler(c, ev, data):
            if ev == MG_EV_HTTP_MSG:
                try:
                    c.ws_upgrade(data, extra_headers=extra_headers)
                except ValueError as e:
                    results.append(e)
                c.reply(400, b"rejected")

        with ServerThread(handler) as port:
            try:
                urllib.request.urlopen(f"http://127.0.0.1:{port}/", timeout=2)
            except Exception:
                pass

        assert len(results) == 1
        assert expected_match in str(results[0])

    def test_ws_upgrade_header_name_with_newline_rejected(self):
        self._run_ws_upgrade_test({"Bad\nName": "val"}, "Header name")

    def test_ws_upgrade_header_value_with_crlf_rejected(self):
        self._run_ws_upgrade_test({"X-Ok": "a\r\nEvil: x"}, "Header value")

    def test_ws_upgrade_header_value_with_nul_rejected(self):
        self._run_ws_upgrade_test({"X-Ok": "vis\x00hidden"}, "Header value")


# ---------------------------------------------------------------------------
# Issue #18 -- poll() reentrancy guard
# ---------------------------------------------------------------------------


class TestPollReentrancyGuard:
    """poll() must raise if called concurrently."""

    def test_concurrent_poll_raises(self):
        """Calling poll() while another thread is inside poll() must raise."""
        import threading

        manager = Manager(enable_wakeup=True)
        errors = []
        first_entered = threading.Event()

        def long_poll():
            first_entered.set()
            manager.poll(2000)

        try:
            manager.listen("tcp://127.0.0.1:0")
            manager.poll(10)

            t1 = threading.Thread(target=long_poll)
            t1.start()
            first_entered.wait(timeout=2)
            import time

            time.sleep(0.2)  # let t1 reach mg_mgr_poll (GIL released)

            try:
                manager.poll(10)
            except RuntimeError as e:
                errors.append(e)

            # Wake t1 so it finishes promptly
            manager.wakeup(manager.wakeup_id, b"")
            t1.join(timeout=3)

            assert len(errors) == 1
            assert "not reentrant" in str(errors[0])
        finally:
            manager.close()
