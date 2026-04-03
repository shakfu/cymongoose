#!/usr/bin/env python3
"""Functional tests for the micro web-framework example."""

import json
import sys
import threading
import time
import urllib.request
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))
sys.path.insert(0, str(Path(__file__).parent / "http"))

from http_web_framework import App, Response, json_response

from cymongoose import Manager

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_request(port, path, method="GET", body=None, headers=None):
    """Send an HTTP request and return (status, body_str, response_headers)."""
    url = f"http://127.0.0.1:{port}{path}"
    data = body.encode() if isinstance(body, str) else body
    req = urllib.request.Request(url, data=data, method=method)
    for k, v in (headers or {}).items():
        req.add_header(k, v)
    try:
        resp = urllib.request.urlopen(req, timeout=2)
        return resp.status, resp.read().decode(), dict(resp.headers)
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode(), dict(e.headers)


class _Server:
    """Context manager that runs an App on a random port in a background thread."""

    def __init__(self, app):
        self.app = app
        self.mgr = Manager(app.handler)
        self._stop = threading.Event()
        self._thread = None

    def __enter__(self):
        conn = self.mgr.listen("http://127.0.0.1:0")
        self.port = conn.local_addr[1]
        self._thread = threading.Thread(target=self._poll, daemon=True)
        self._thread.start()
        time.sleep(0.15)
        return self

    def __exit__(self, *exc):
        self._stop.set()
        self._thread.join(timeout=2)
        self.mgr.close()

    def _poll(self):
        while not self._stop.is_set():
            self.mgr.poll(50)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestRouting:
    """Basic route matching and method dispatch."""

    @pytest.fixture(autouse=True)
    def _setup(self):
        self.app = App()

        @self.app.get("/")
        def index(req):
            return "index"

        @self.app.get("/hello/<name>")
        def hello(req, name):
            return json_response({"hello": name})

        @self.app.post("/echo")
        def echo(req):
            return json_response(req.json(), status=201)

        with _Server(self.app) as srv:
            self.port = srv.port
            yield

    def test_index(self):
        status, body, _ = _make_request(self.port, "/")
        assert status == 200
        assert body == "index"

    def test_path_param(self):
        status, body, _ = _make_request(self.port, "/hello/world")
        assert status == 200
        data = json.loads(body)
        assert data == {"hello": "world"}

    def test_post_echo(self):
        payload = json.dumps({"key": "value"})
        status, body, hdrs = _make_request(
            self.port,
            "/echo",
            method="POST",
            body=payload,
            headers={"Content-Type": "application/json"},
        )
        assert status == 201
        assert json.loads(body) == {"key": "value"}

    def test_method_not_matched(self):
        """POST to a GET-only route should 404."""
        status, _, _ = _make_request(self.port, "/", method="POST")
        assert status == 404

    def test_unknown_path(self):
        status, _, _ = _make_request(self.port, "/nope")
        assert status == 404


class TestIntPathParam:
    """Integer path parameters and conversion failure."""

    @pytest.fixture(autouse=True)
    def _setup(self):
        self.app = App()

        @self.app.get("/items/<int:id>")
        def get_item(req, id):
            return json_response({"id": id, "type": type(id).__name__})

        with _Server(self.app) as srv:
            self.port = srv.port
            yield

    def test_int_param(self):
        status, body, _ = _make_request(self.port, "/items/42")
        assert status == 200
        data = json.loads(body)
        assert data == {"id": 42, "type": "int"}

    def test_non_int_param_gives_404(self):
        """A non-numeric segment should not match <int:id>."""
        status, _, _ = _make_request(self.port, "/items/abc")
        assert status == 404


class TestCRUD:
    """End-to-end CRUD using the demo items store."""

    @pytest.fixture(autouse=True)
    def _setup(self):
        self.app = App()
        store = []

        @self.app.get("/items")
        def list_items(req):
            return json_response(store)

        @self.app.post("/items")
        def create(req):
            item = req.json()
            if item is None:
                return Response("bad json", status=400)
            store.append(item)
            return json_response(item, status=201)

        @self.app.get("/items/<int:id>")
        def get(req, id):
            if 0 <= id < len(store):
                return json_response(store[id])
            return json_response({"error": "not found"}, status=404)

        @self.app.delete("/items/<int:id>")
        def remove(req, id):
            if 0 <= id < len(store):
                return json_response(store.pop(id))
            return json_response({"error": "not found"}, status=404)

        with _Server(self.app) as srv:
            self.port = srv.port
            yield

    def test_empty_list(self):
        status, body, _ = _make_request(self.port, "/items")
        assert status == 200
        assert json.loads(body) == []

    def test_create_and_get(self):
        payload = json.dumps({"name": "widget"})
        s1, _, _ = _make_request(
            self.port,
            "/items",
            method="POST",
            body=payload,
            headers={"Content-Type": "application/json"},
        )
        assert s1 == 201

        s2, body, _ = _make_request(self.port, "/items/0")
        assert s2 == 200
        assert json.loads(body) == {"name": "widget"}

    def test_delete(self):
        payload = json.dumps({"name": "gizmo"})
        _make_request(
            self.port,
            "/items",
            method="POST",
            body=payload,
            headers={"Content-Type": "application/json"},
        )
        s, body, _ = _make_request(self.port, "/items/0", method="DELETE")
        assert s == 200
        assert json.loads(body) == {"name": "gizmo"}

        # List should be empty now
        s2, body2, _ = _make_request(self.port, "/items")
        assert json.loads(body2) == []

    def test_get_missing_item(self):
        status, body, _ = _make_request(self.port, "/items/99")
        assert status == 404


class TestHooks:
    """Before/after request hooks."""

    @pytest.fixture(autouse=True)
    def _setup(self):
        self.app = App()

        @self.app.before_request
        def add_marker(req):
            req.extras = {"hooked": True}

        @self.app.after_request
        def add_header(req, resp):
            resp.headers["X-Hooked"] = "true"
            return resp

        @self.app.get("/check")
        def check(req):
            hooked = getattr(req, "extras", {}).get("hooked", False)
            return json_response({"before_hook_ran": hooked})

        with _Server(self.app) as srv:
            self.port = srv.port
            yield

    def test_before_hook(self):
        status, body, _ = _make_request(self.port, "/check")
        assert status == 200
        assert json.loads(body)["before_hook_ran"] is True

    def test_after_hook_header(self):
        _, _, hdrs = _make_request(self.port, "/check")
        assert hdrs.get("X-Hooked") == "true"


class TestCustomNotFound:
    """Custom 404 handler."""

    @pytest.fixture(autouse=True)
    def _setup(self):
        self.app = App()

        @self.app.not_found
        def nf(req):
            return Response(
                json.dumps({"error": "custom 404", "path": req.uri}),
                status=404,
                headers={"Content-Type": "application/json"},
            )

        with _Server(self.app) as srv:
            self.port = srv.port
            yield

    def test_custom_404_body(self):
        status, body, _ = _make_request(self.port, "/missing")
        assert status == 404
        data = json.loads(body)
        assert data["error"] == "custom 404"
        assert data["path"] == "/missing"


class TestResponseShortcuts:
    """Handler return-value coercion (str, dict, tuple)."""

    @pytest.fixture(autouse=True)
    def _setup(self):
        self.app = App()

        @self.app.get("/str")
        def ret_str(req):
            return "plain"

        @self.app.get("/dict")
        def ret_dict(req):
            return {"a": 1}

        @self.app.get("/tuple")
        def ret_tuple(req):
            return "created", 201

        @self.app.get("/dict-tuple")
        def ret_dict_tuple(req):
            return {"b": 2}, 202

        @self.app.get("/none")
        def ret_none(req):
            pass  # implicitly returns None

        with _Server(self.app) as srv:
            self.port = srv.port
            yield

    def test_str_response(self):
        s, body, _ = _make_request(self.port, "/str")
        assert s == 200 and body == "plain"

    def test_dict_response(self):
        s, body, _ = _make_request(self.port, "/dict")
        assert s == 200
        assert json.loads(body) == {"a": 1}

    def test_tuple_response(self):
        s, body, _ = _make_request(self.port, "/tuple")
        assert s == 201 and body == "created"

    def test_dict_tuple_response(self):
        s, body, _ = _make_request(self.port, "/dict-tuple")
        assert s == 202
        assert json.loads(body) == {"b": 2}

    def test_none_response(self):
        s, body, _ = _make_request(self.port, "/none")
        assert s == 200


class TestMultipleMethods:
    """A single route pattern with multiple methods."""

    @pytest.fixture(autouse=True)
    def _setup(self):
        self.app = App()

        @self.app.route("/resource", methods=["GET", "POST"])
        def resource(req):
            return json_response({"method": req.method})

        with _Server(self.app) as srv:
            self.port = srv.port
            yield

    def test_get(self):
        s, body, _ = _make_request(self.port, "/resource")
        assert s == 200
        assert json.loads(body)["method"] == "GET"

    def test_post(self):
        s, body, _ = _make_request(self.port, "/resource", method="POST")
        assert s == 200
        assert json.loads(body)["method"] == "POST"

    def test_put_not_allowed(self):
        s, _, _ = _make_request(self.port, "/resource", method="PUT")
        assert s == 404


if __name__ == "__main__":
    result = pytest.main([__file__, "-v"])
    sys.exit(result)
