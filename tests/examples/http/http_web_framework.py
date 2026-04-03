#!/usr/bin/env python3
"""Minimal web framework built on cymongoose.

This example demonstrates how to build a Flask/Bottle-style micro-framework
on top of cymongoose's event loop. It provides:

1. Decorator-based routing (@app.route, @app.get, @app.post, etc.)
2. Path parameters with type conversion (/users/<int:id>)
3. JSON request parsing and response helpers
4. Method-specific handlers
5. Before/after request hooks

Usage:
    python http_web_framework.py [-l LISTEN_URL]

Example:
    python http_web_framework.py -l http://0.0.0.0:8000

    curl http://localhost:8000/
    curl http://localhost:8000/greet/world
    curl http://localhost:8000/items
    curl -X POST -H "Content-Type: application/json" \
         -d '{"name":"widget","price":9.99}' http://localhost:8000/items
    curl http://localhost:8000/items/0
    curl -X DELETE http://localhost:8000/items/0
"""

import argparse
import json
import re
import signal
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent / "src"))

from cymongoose import MG_EV_HTTP_MSG, Manager

# ---------------------------------------------------------------------------
# Micro-framework core
# ---------------------------------------------------------------------------

# Converters for path parameters: <type:name>
_CONVERTERS = {
    "str": (r"([^/]+)", str),
    "int": (r"(\d+)", int),
    "path": (r"(.+)", str),
}

# Matches <name> or <type:name>
_PARAM_RE = re.compile(r"<(?:(\w+):)?(\w+)>")


def _compile_route(pattern):
    """Compile a route pattern into a regex and a list of (name, converter) pairs.

    Examples:
        "/users/<int:id>"  -> regex, [("id", int)]
        "/greet/<name>"    -> regex, [("name", str)]
    """
    params = []
    regex = "^"
    pos = 0
    for m in _PARAM_RE.finditer(pattern):
        regex += re.escape(pattern[pos : m.start()])
        type_name = m.group(1) or "str"
        param_name = m.group(2)
        type_regex, converter = _CONVERTERS[type_name]
        regex += type_regex
        params.append((param_name, converter))
        pos = m.end()
    regex += re.escape(pattern[pos:]) + "$"
    return re.compile(regex), params


class Request:
    """Thin wrapper around an HttpMessage for framework consumers."""

    __slots__ = ("method", "uri", "query", "headers_raw", "body_bytes", "body_text",
                 "_hm", "path_params", "extras")

    def __init__(self, hm):
        self._hm = hm
        self.method = hm.method
        self.uri = hm.uri
        self.query = hm.query
        self.headers_raw = hm.headers()
        self.body_bytes = hm.body_bytes
        self.body_text = hm.body_text
        self.path_params = {}
        self.extras = {}

    def header(self, name, default=None):
        return self._hm.header(name, default=default)

    def json(self):
        """Parse request body as JSON. Returns None on failure."""
        try:
            return json.loads(self.body_text)
        except (json.JSONDecodeError, ValueError):
            return None

    def query_var(self, name, default=None):
        val = self._hm.query_var(name)
        return val if val is not None else default


class Response:
    """Simple response object."""

    __slots__ = ("status", "body", "headers")

    def __init__(self, body="", status=200, headers=None):
        self.status = status
        self.body = body
        self.headers = headers or {}


def json_response(data, status=200):
    """Helper to create a JSON response."""
    return Response(
        body=json.dumps(data),
        status=status,
        headers={"Content-Type": "application/json"},
    )


class App:
    """A minimal web framework on top of cymongoose.

    Usage::

        app = App()

        @app.get("/")
        def index(req):
            return Response("Hello")

        @app.get("/users/<int:id>")
        def get_user(req, id):
            return json_response({"id": id})

        app.run()
    """

    def __init__(self):
        self._routes = []  # list of (compiled_re, params, method, handler)
        self._before_hooks = []
        self._after_hooks = []
        self._not_found = None

    # -- Routing decorators --------------------------------------------------

    def route(self, pattern, methods=None):
        """Register a handler for *pattern* accepting the given HTTP methods."""
        methods = [m.upper() for m in (methods or ["GET"])]

        def decorator(fn):
            compiled, params = _compile_route(pattern)
            for method in methods:
                self._routes.append((compiled, params, method, fn))
            return fn

        return decorator

    def get(self, pattern):
        return self.route(pattern, methods=["GET"])

    def post(self, pattern):
        return self.route(pattern, methods=["POST"])

    def put(self, pattern):
        return self.route(pattern, methods=["PUT"])

    def delete(self, pattern):
        return self.route(pattern, methods=["DELETE"])

    def not_found(self, fn):
        """Register a custom 404 handler."""
        self._not_found = fn
        return fn

    def before_request(self, fn):
        """Register a hook that runs before every matched handler."""
        self._before_hooks.append(fn)
        return fn

    def after_request(self, fn):
        """Register a hook that runs after every matched handler.

        The hook receives (request, response) and must return a Response.
        """
        self._after_hooks.append(fn)
        return fn

    # -- Internal dispatch ----------------------------------------------------

    def _dispatch(self, conn, hm):
        """Match a request to a handler and send the response."""
        req = Request(hm)

        for compiled, params, method, handler in self._routes:
            if method != req.method:
                continue
            m = compiled.match(req.uri)
            if m:
                kwargs = {}
                for i, (name, converter) in enumerate(params):
                    try:
                        kwargs[name] = converter(m.group(i + 1))
                    except (ValueError, TypeError):
                        # Conversion failed (e.g. non-integer for <int:id>)
                        self._send(conn, Response("Bad Request", status=400))
                        return
                req.path_params = kwargs

                for hook in self._before_hooks:
                    hook(req)

                resp = handler(req, **kwargs)
                if resp is None:
                    resp = Response("")
                elif isinstance(resp, str):
                    resp = Response(resp)
                elif isinstance(resp, dict):
                    resp = json_response(resp)
                elif isinstance(resp, tuple):
                    body, status = resp
                    if isinstance(body, dict):
                        resp = json_response(body, status)
                    else:
                        resp = Response(body, status)

                for hook in self._after_hooks:
                    resp = hook(req, resp)

                self._send(conn, resp)
                return

        # No route matched
        if self._not_found:
            resp = self._not_found(req)
            if isinstance(resp, str):
                resp = Response(resp, status=404)
        else:
            resp = Response("Not Found", status=404)
        self._send(conn, resp)

    @staticmethod
    def _send(conn, resp):
        conn.reply(resp.status, resp.body, headers=resp.headers or None)

    def handler(self, conn, event, data):
        """cymongoose event handler -- wire this into a Manager."""
        if event == MG_EV_HTTP_MSG:
            self._dispatch(conn, data)

    # -- Convenience runner ---------------------------------------------------

    def run(self, listen="http://0.0.0.0:8000", poll_ms=100):
        """Blocking helper that creates a Manager and runs the event loop."""
        shutdown = False

        def on_signal(sig, frame):
            nonlocal shutdown
            shutdown = True

        signal.signal(signal.SIGINT, on_signal)
        signal.signal(signal.SIGTERM, on_signal)

        mgr = Manager(self.handler)
        mgr.listen(listen)

        print(f"Listening on {listen}  (Ctrl+C to stop)")
        try:
            while not shutdown:
                mgr.poll(poll_ms)
        finally:
            mgr.close()
            print("Server stopped.")


# ---------------------------------------------------------------------------
# Demo application
# ---------------------------------------------------------------------------

app = App()

# In-memory store for the demo
items = []


@app.get("/")
def index(req):
    return Response(
        "<h1>cymongoose micro-framework</h1>"
        "<p>Try /greet/world, /items, POST /items</p>",
        headers={"Content-Type": "text/html"},
    )


@app.get("/greet/<name>")
def greet(req, name):
    return json_response({"greeting": f"Hello, {name}!"})


@app.get("/items")
def list_items(req):
    return json_response(items)


@app.post("/items")
def create_item(req):
    body = req.json()
    if body is None:
        return Response("Invalid JSON", status=400)
    items.append(body)
    return json_response(body, status=201)


@app.get("/items/<int:id>")
def get_item(req, id):
    if 0 <= id < len(items):
        return json_response(items[id])
    return json_response({"error": "not found"}, status=404)


@app.delete("/items/<int:id>")
def delete_item(req, id):
    if 0 <= id < len(items):
        removed = items.pop(id)
        return json_response(removed)
    return json_response({"error": "not found"}, status=404)


@app.not_found
def custom_404(req):
    return Response(
        json.dumps({"error": "not found", "path": req.uri}),
        status=404,
        headers={"Content-Type": "application/json"},
    )


def main():
    parser = argparse.ArgumentParser(description="Micro-framework demo")
    parser.add_argument(
        "-l", "--listen", default="http://0.0.0.0:8000",
        help="Listen URL (default: http://0.0.0.0:8000)",
    )
    args = parser.parse_args()
    app.run(listen=args.listen)


if __name__ == "__main__":
    main()
