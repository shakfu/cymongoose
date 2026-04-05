# TODO

## Upstream: Mongoose 7.19 -> 7.21

- [x] **Vendor mongoose 7.21** (High)
  Replace `thirdparty/mongoose/mongoose.{c,h}` with 7.21 sources.
  Rebuild and run full test suite. Key bug fixes:
  - HTTP fast closure handling improvements
  - `mg_aton()` IPv6 scope ID fix (affects `conn.local_addr`/`conn.remote_addr`)
  - Long-standing certificate verification failure causing random verify errors
  - `mg_queue_vprintf` va_args fix (compiler-dependent correctness)
  - CVE-2025-65502: `SSL_CTX_get_cert_store()` crash under low RAM (OpenSSL only)

- [x] **Verify `c->loc` semantic change** (High)
  7.21 changes `c->loc` on accepted TCP connections from the listener's
  bind address (e.g. `0.0.0.0`) to the actual local address the client
  connected to. Verify `conn.local_addr` tests still pass and update
  expectations if needed.

- [x] **Expose `mg_mqtt_unsub()`** (Low)
  7.21 adds `mg_mqtt_unsub()` for MQTT unsubscribe. Bind it in
  `_mongoose.pyx` and expose as `conn.mqtt_unsub()`. This completes the
  existing MQTT API surface rather than adding a new protocol.

## Feature Gaps (mongoose API not yet exposed)

- [x] **MQTT v5 property access** (High)
  Expose `mg_mqtt_next_prop()` and the `mg_mqtt_prop` struct so users can
  iterate MQTT v5 properties. The `is_mqtt5` flag is already on
  `Connection` but there is no way to read properties from messages.

- [x] **RPC framework** (Medium)
  Expose `mg_rpc_add`, `mg_rpc_del`, `mg_rpc_process`, `mg_rpc_ok`,
  `mg_rpc_err`, `mg_rpc_list`. Mongoose ships a built-in JSON-RPC
  framework that could save users significant boilerplate for
  request/response APIs.

- [x] **URL parsing utilities** (Medium)
  Expose `mg_url_port`, `mg_url_host`, `mg_url_user`, `mg_url_pass`,
  `mg_url_uri`, `mg_url_is_ssl`. Currently only `mg_url_encode` is
  wrapped. These are handy for decomposing URLs without pulling in
  `urllib.parse`.

- [x] **`mg_match` glob-style pattern matching** (Medium)
  Expose `mg_match` (and possibly `mg_span`). Useful for route matching
  inside event handlers without reimplementing glob logic in Python.

- [x] **`mg_http_var`** (Low)
  Newer alternative to `mg_http_get_var` for extracting form/query
  variables. The older function is already wrapped; this one returns an
  `mg_str` instead of writing to a fixed buffer.

- [x] **Hashing utilities** (Low)
  Expose `mg_sha256`, `mg_hmac_sha256`, `mg_sha1_*`, `mg_md5_*`.
  Useful if users want lightweight hashing without importing `hashlib`,
  though Python's stdlib already covers this well.

- [x] **Base64 encode/decode** (Low)
  Expose `mg_base64_encode`, `mg_base64_decode`. Same rationale as
  hashing -- convenient but redundant with Python's `base64` module.

- [x] **Misc small utilities** (Low)
  Expose `mg_millis`, `mg_random`, `mg_random_str`, `mg_crc32`.
  Minor convenience; Python equivalents exist (`time.monotonic_ns`,
  `os.urandom`, `binascii.crc32`).
