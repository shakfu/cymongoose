#!/usr/bin/env python3
"""Flask HTTP server for performance benchmarking."""

from flask import Flask, jsonify

app = Flask(__name__)


@app.route("/", methods=["GET", "POST"])
def root():
    """Simple JSON response handler."""
    return jsonify({"message": "Hello, World!"})


def run_server(port: int = 8004):
    """Run Flask HTTP server."""
    print(f"Flask server listening on http://0.0.0.0:{port}")
    app.run(host="0.0.0.0", port=port, threaded=True)


if __name__ == "__main__":
    import sys

    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8004
    run_server(port)
