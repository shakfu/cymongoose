# TODO

## Upstream: Mongoose 7.19 -> 7.21

- [ ] **Vendor mongoose 7.21** (High)
  Replace `thirdparty/mongoose/mongoose.{c,h}` with 7.21 sources.
  Rebuild and run full test suite. Key bug fixes:
  - HTTP fast closure handling improvements
  - `mg_aton()` IPv6 scope ID fix (affects `conn.local_addr`/`conn.remote_addr`)
  - Long-standing certificate verification failure causing random verify errors
  - `mg_queue_vprintf` va_args fix (compiler-dependent correctness)
  - CVE-2025-65502: `SSL_CTX_get_cert_store()` crash under low RAM (OpenSSL only)

- [ ] **Verify `c->loc` semantic change** (High)
  7.21 changes `c->loc` on accepted TCP connections from the listener's
  bind address (e.g. `0.0.0.0`) to the actual local address the client
  connected to. Verify `conn.local_addr` tests still pass and update
  expectations if needed.

- [ ] **Expose `mg_mqtt_unsub()`** (Low)
  7.21 adds `mg_mqtt_unsub()` for MQTT unsubscribe. Bind it in
  `_mongoose.pyx` and expose as `conn.mqtt_unsub()`. This completes the
  existing MQTT API surface rather than adding a new protocol.
