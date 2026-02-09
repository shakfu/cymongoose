#!/usr/bin/env python3
"""FastAPI/uvicorn HTTP server for performance benchmarking."""

import uvicorn
from fastapi import FastAPI

app = FastAPI()


@app.get("/")
@app.post("/")
async def root():
    """Simple JSON response handler."""
    return {"message": "Hello, World!"}


def run_server(port: int = 8003):
    """Run FastAPI/uvicorn HTTP server."""
    print(f"uvicorn server listening on http://0.0.0.0:{port}")
    uvicorn.run(app, host="0.0.0.0", port=port, log_level="error")


if __name__ == "__main__":
    import sys

    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8003
    run_server(port)
