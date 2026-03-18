"""Tests for Connection.serve_dir() and Connection.serve_file()."""

import urllib.request

from cymongoose import MG_EV_HTTP_MSG
from tests.conftest import ServerThread


class TestServeDir:
    """serve_dir() serves files from a directory."""

    def test_serve_text_file(self, tmp_path):
        (tmp_path / "hello.txt").write_text("hello world")

        def handler(conn, ev, data):
            if ev == MG_EV_HTTP_MSG:
                conn.serve_dir(data, str(tmp_path))

        with ServerThread(handler) as port:
            resp = urllib.request.urlopen(f"http://127.0.0.1:{port}/hello.txt", timeout=2)
            body = resp.read()
            assert body == b"hello world"

    def test_serve_binary_file(self, tmp_path):
        content = bytes(range(256))
        (tmp_path / "data.bin").write_bytes(content)

        def handler(conn, ev, data):
            if ev == MG_EV_HTTP_MSG:
                conn.serve_dir(data, str(tmp_path))

        with ServerThread(handler) as port:
            resp = urllib.request.urlopen(f"http://127.0.0.1:{port}/data.bin", timeout=2)
            body = resp.read()
            assert body == content

    def test_serve_nested_file(self, tmp_path):
        sub = tmp_path / "sub"
        sub.mkdir()
        (sub / "nested.txt").write_text("nested content")

        def handler(conn, ev, data):
            if ev == MG_EV_HTTP_MSG:
                conn.serve_dir(data, str(tmp_path))

        with ServerThread(handler) as port:
            resp = urllib.request.urlopen(f"http://127.0.0.1:{port}/sub/nested.txt", timeout=2)
            assert resp.read() == b"nested content"

    def test_serve_nonexistent_returns_404(self, tmp_path):
        (tmp_path / "exists.txt").write_text("ok")

        def handler(conn, ev, data):
            if ev == MG_EV_HTTP_MSG:
                conn.serve_dir(data, str(tmp_path))

        with ServerThread(handler) as port:
            try:
                urllib.request.urlopen(f"http://127.0.0.1:{port}/no-such-file.txt", timeout=2)
                assert False, "Should have raised HTTPError"
            except urllib.error.HTTPError as e:
                assert e.code == 404

    def test_serve_html_content_type(self, tmp_path):
        (tmp_path / "page.html").write_text("<h1>hi</h1>")

        def handler(conn, ev, data):
            if ev == MG_EV_HTTP_MSG:
                conn.serve_dir(data, str(tmp_path))

        with ServerThread(handler) as port:
            resp = urllib.request.urlopen(f"http://127.0.0.1:{port}/page.html", timeout=2)
            ct = resp.headers.get("Content-Type", "")
            assert "text/html" in ct

    def test_serve_extra_headers(self, tmp_path):
        (tmp_path / "f.txt").write_text("x")

        def handler(conn, ev, data):
            if ev == MG_EV_HTTP_MSG:
                conn.serve_dir(
                    data,
                    str(tmp_path),
                    extra_headers="X-Custom: test-value\r\n",
                )

        with ServerThread(handler) as port:
            resp = urllib.request.urlopen(f"http://127.0.0.1:{port}/f.txt", timeout=2)
            assert resp.headers.get("X-Custom") == "test-value"

    def test_serve_custom_404_page(self, tmp_path):
        (tmp_path / "custom404.html").write_text("custom not found")

        def handler(conn, ev, data):
            if ev == MG_EV_HTTP_MSG:
                conn.serve_dir(
                    data,
                    str(tmp_path),
                    page404=str(tmp_path / "custom404.html"),
                )

        with ServerThread(handler) as port:
            resp = urllib.request.urlopen(f"http://127.0.0.1:{port}/missing.txt", timeout=2)
            body = resp.read()
            assert b"custom not found" in body


class TestServeFile:
    """serve_file() serves a single specific file regardless of URI."""

    def test_serve_specific_file(self, tmp_path):
        target = tmp_path / "target.txt"
        target.write_text("specific file content")

        def handler(conn, ev, data):
            if ev == MG_EV_HTTP_MSG:
                conn.serve_file(data, str(target))

        with ServerThread(handler) as port:
            resp = urllib.request.urlopen(f"http://127.0.0.1:{port}/anything", timeout=2)
            assert resp.read() == b"specific file content"

    def test_serve_file_ignores_uri(self, tmp_path):
        """serve_file always serves the same file regardless of request URI."""
        target = tmp_path / "fixed.txt"
        target.write_text("always this")

        def handler(conn, ev, data):
            if ev == MG_EV_HTTP_MSG:
                conn.serve_file(data, str(target))

        with ServerThread(handler) as port:
            for path in ["/", "/foo", "/bar/baz"]:
                resp = urllib.request.urlopen(f"http://127.0.0.1:{port}{path}", timeout=2)
                assert resp.read() == b"always this"

    def test_serve_file_extra_headers(self, tmp_path):
        target = tmp_path / "dl.bin"
        target.write_bytes(b"\x00\x01\x02")

        def handler(conn, ev, data):
            if ev == MG_EV_HTTP_MSG:
                conn.serve_file(
                    data,
                    str(target),
                    extra_headers="Content-Disposition: attachment\r\n",
                )

        with ServerThread(handler) as port:
            resp = urllib.request.urlopen(f"http://127.0.0.1:{port}/dl.bin", timeout=2)
            assert resp.headers.get("Content-Disposition") == "attachment"
            assert resp.read() == b"\x00\x01\x02"

    def test_serve_nonexistent_file_returns_404(self, tmp_path):
        def handler(conn, ev, data):
            if ev == MG_EV_HTTP_MSG:
                conn.serve_file(data, str(tmp_path / "nope.txt"))

        with ServerThread(handler) as port:
            try:
                urllib.request.urlopen(f"http://127.0.0.1:{port}/", timeout=2)
                assert False, "Should have raised HTTPError"
            except urllib.error.HTTPError as e:
                assert e.code == 404
