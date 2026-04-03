# ASGI Framework Support (Planned)

An ASGI server adapter for async Python web frameworks is planned.
It will allow FastAPI, Starlette, Django (async mode), and Quart
applications to run on cymongoose's C event loop, similar to how
the [WSGI adapter](wsgi.md) supports synchronous frameworks.

## Planned Scope

- **HTTP sub-protocol**: async request/response lifecycle.
- **WebSocket sub-protocol**: upgrade, send, receive, disconnect --
  mapping directly to cymongoose's `ws_upgrade()` and `MG_EV_WS_MSG`.
- **Lifespan sub-protocol**: application startup/shutdown hooks.

## Architecture Notes

The ASGI adapter will build on `AsyncManager` and cymongoose's native
WebSocket support.  Unlike the WSGI adapter (which bridges blocking
callables via a thread pool), the ASGI adapter can run coroutines
directly on the asyncio event loop, avoiding the thread-pool overhead.

Track progress in the project's `TODO.md`.

## See Also

- [WSGI Support](wsgi.md) -- synchronous framework adapter (Flask, Django, Bottle)
- [HTTP/HTTPS Guide](http.md) -- raw event handler approach
- [AsyncManager API](../api/async_manager.md) -- asyncio integration
