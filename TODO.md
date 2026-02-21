# TODO

## Code

- [x] **Skip `_wrap_event_data` for data-less events** -- `_event_bridge` now skips `_wrap_event_data` for events that never carry data (POLL, WRITE, OPEN, CLOSE, ACCEPT, CONNECT, READ, TLS_HS, RESOLVE, WS_CTL) via `_ev_has_data()` guard.

- [x] **Comment `uintptr_t` key reuse safety in `_connections`** -- added comment on `_ensure_connection` explaining why `uintptr_t` keys are safe: `_drop_connection` removes the entry on `MG_EV_CLOSE` before the C struct is freed, and Mongoose's single-threaded event loop prevents same-cycle address reuse.

- [ ] **Improve `AsyncManager` lock granularity** -- `AsyncManager._run()` holds `self._lock` for the entire duration of `poll()` (up to `poll_interval` ms). All delegated methods (`listen`, `connect`, etc.) also acquire the lock, meaning they block until `poll()` returns. For `poll_interval=100`, that's up to 100ms latency per operation. Consider using `wakeup()` to interrupt the poll loop, or document the latency and recommend calling `listen()`/`connect()` at startup only.

- [x] **Make `reply()` Content-Type default consistent** -- `reply()` now adds `Content-Type: text/plain` as a fallback when a user-provided `headers` dict omits a `Content-Type` key (case-insensitive check). Updated docstring in `.pyi` stub.

- [x] **Document listener port discovery in `listen()` docstring** -- added code example to `listen()` docstring showing `listener.local_addr[1]` for OS-assigned ports. Updated both `.pyx` and `.pyi`.

## Testing

- [x] **Add negative/adversarial tests** -- malformed HTTP requests, invalid WebSocket frames, oversized headers, connection flooding. (`tests/test_adversarial.py`, 12 tests)

- [x] **Add concurrent client tests** -- all HTTP tests currently use a single sequential `urllib` client. (`tests/test_concurrent_clients.py`, 6 tests)

- [x] **Add test for `AsyncManager.schedule()`** -- Already covered by `test_async_manager_schedule` (callback) and `test_async_manager_schedule_coroutine` (coroutine) in `tests/test_asyncio_integration.py`.

- [ ] **Add stress test for connection churn** -- The concurrent tests use 50-100 connections. A stress test with thousands of rapid connect/disconnect cycles would better exercise the `_connections` dict and GC interaction.

## Documentation

- [ ] **Deploy Sphinx docs** to ReadTheDocs or GitHub Pages so users can browse the API reference without building locally.

- [ ] **Update documentation URL** in `pyproject.toml` to point to hosted docs instead of the GitHub repo.

- [ ] **Deduplicate README.md and Sphinx docs** -- README duplicates much of the Sphinx content. Consider having the README link to hosted docs for details.
