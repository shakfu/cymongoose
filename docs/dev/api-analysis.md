# Mongoose API Wrapper Analysis

This document tracks which Mongoose C library features are wrapped in cymongoose and prioritizes future work.

## Currently Wrapped Features

### Core Networking

- **Manager** (`mg_mgr`): Event loop management
  - `mg_mgr_init()`, `mg_mgr_free()`, `mg_mgr_poll()`
- **Connection** (`mg_connection`): Connection lifecycle
  - `mg_listen()`, `mg_connect()`, `mg_send()`, `mg_close_conn()`, `mg_printf()`
- **Connection properties**: `is_listening`, `is_closing`

### HTTP Protocol

- **Server/Client**: `mg_http_listen()`, `mg_http_connect()`
- **Response**: `mg_http_reply()`
- **Static files**: `mg_http_serve_dir()`
- **Parsing**: `mg_http_parse()`, `mg_http_get_request_len()`
- **Headers**: `mg_http_get_header()`
- **Query params**: `mg_http_get_var()`
- **Chunked transfer**: `mg_http_printf_chunk()`, `mg_http_write_chunk()`, `mg_http_delete_chunk()`
- **Uploads**: `mg_http_upload()`
- **Auth**: `mg_http_bauth()`, `mg_http_creds()`
- **URL utilities**: `mg_url_decode()`
- **HttpMessage wrapper**: method, uri, query, proto, body, headers

### WebSocket Protocol

- **Client**: `mg_ws_connect()`
- **Server**: `mg_ws_upgrade()`
- **Send**: `mg_ws_send()`, `mg_ws_printf()`
- **WsMessage wrapper**: data, text, flags

### TLS/SSL

- **Declared but not exposed**: `mg_tls_init()`, `mg_tls_free()`, `mg_tls_opts`

### Events (all wrapped)

- Connection: `MG_EV_ERROR`, `MG_EV_OPEN`, `MG_EV_POLL`, `MG_EV_RESOLVE`, `MG_EV_CONNECT`, `MG_EV_ACCEPT`, `MG_EV_CLOSE`, `MG_EV_READ`, `MG_EV_WRITE`
- TLS: `MG_EV_TLS_HS`
- HTTP: `MG_EV_HTTP_HDRS`, `MG_EV_HTTP_MSG`
- WebSocket: `MG_EV_WS_OPEN`, `MG_EV_WS_MSG`, `MG_EV_WS_CTL`
- Other: `MG_EV_WAKEUP`, `MG_EV_USER`
- MQTT (declared): `MG_EV_MQTT_CMD`, `MG_EV_MQTT_MSG`, `MG_EV_MQTT_OPEN`
- SNTP (declared): `MG_EV_SNTP_TIME`

## Unwrapped Features - Priority Analysis

### High Priority (Essential for Production Use)

#### 1. Error Handling & Diagnostics

**Why**: Critical for debugging and production monitoring

- `mg_error()` - Programmatically trigger error events
- Connection state flags: `is_client`, `is_tls`, `is_udp`, `is_websocket`, `is_readable`, `is_writable`
- `mg_addr` access - Expose connection local/remote addresses (ip, port, is_ip6)
- Connection ID - Already available via `mg_connection.id`

**Impact**: Enables proper error handling, logging, and diagnostics

#### 2. HTTP Essential Features

**Why**: Common HTTP use cases not yet covered

- `mg_http_serve_file()` - Serve single file (complement to serve_dir)
- `mg_http_status()` - Parse status code from HTTP response
- `mg_http_var()` - Parse query/form variables without buffer
- `mg_http_get_header_var()` - Parse header sub-values (e.g., charset from Content-Type)
- `mg_url_encode()` - URL encoding (decode already wrapped)
- `mg_http_next_multipart()` + `mg_http_part` - Parse multipart form data

**Impact**: Completes HTTP server/client functionality for real-world apps

#### 3. Connection Management

**Why**: Required for thread-safe async operations

- `mg_wakeup()` / `mg_wakeup_init()` - Cross-thread notification (critical for async)
- `mg_iobuf` access - Inspect recv/send buffers (size, len, pending data)
- `mg_vprintf()` - Variadic formatted send (more flexible than mg_printf)

**Impact**: Enables thread-safe designs, better buffer management

#### 4. JSON Utilities

**Why**: HTTP APIs overwhelmingly use JSON

- `mg_json_get()` - Extract JSON value by path (e.g., "$.user.name")
- `mg_json_get_num()`, `mg_json_get_long()`, `mg_json_get_bool()` - Typed extraction
- `mg_json_next()` - Iterate JSON arrays/objects
- `mg_json_unescape()` - Decode JSON strings

**Impact**: Zero-copy JSON parsing for API servers/clients

### Medium Priority (Common Use Cases)

#### 5. MQTT Protocol

**Why**: IoT, messaging, pub/sub architectures

- `mg_mqtt_connect()`, `mg_mqtt_listen()`
- `mg_mqtt_pub()`, `mg_mqtt_sub()`
- `mg_mqtt_login()`, `mg_mqtt_ping()`, `mg_mqtt_pong()`, `mg_mqtt_disconnect()`
- `mg_mqtt_message` struct wrapper
- `mg_mqtt_parse()`, `mg_mqtt_send_header()`
- Events already declared: `MG_EV_MQTT_CMD`, `MG_EV_MQTT_MSG`, `MG_EV_MQTT_OPEN`

**Impact**: Unlocks IoT/messaging use cases

#### 6. DNS/mDNS

**Why**: Service discovery, async DNS resolution

- `mg_resolve()`, `mg_resolve_cancel()` - Non-blocking DNS
- `mg_mdns_listen()` - mDNS service discovery
- `mg_dns_parse()`, `mg_dns_message` - DNS packet handling

**Impact**: Enables service discovery, better connection handling

#### 7. SNTP (Time Synchronization)

**Why**: Time sync for distributed systems

- `mg_sntp_connect()`, `mg_sntp_request()`, `mg_sntp_parse()`
- Event already declared: `MG_EV_SNTP_TIME`

**Impact**: Time synchronization without system dependencies

#### 8. String/Utility Functions

**Why**: Convenience, consistency with Mongoose API

- `mg_str_n()` - Construct mg_str (declared but unused)
- `mg_match()` - Glob/pattern matching
- `mg_strcmp()`, `mg_strcasecmp()` - mg_str comparisons
- `mg_span()` - Split strings by delimiter
- `mg_str_to_num()` - Parse numbers from mg_str

**Impact**: Cleaner API, reduced conversions

#### 9. Timer API

**Why**: Periodic tasks within event loop

- `mg_timer_add()` - Schedule periodic callbacks
- `mg_timer_poll()`, `mg_timer_free()`, `mg_timer_expired()`

**Impact**: Timeouts, periodic tasks without threading

### Low Priority (Specialized/Advanced)

#### 10. TLS Configuration

**Why**: Production HTTPS/WSS requires TLS

- Expose `mg_tls_opts` as Python class (ca, cert, key, name, skip_verification)
- Make `mg_tls_init()` callable from Python
- `mg_tls_send()`, `mg_tls_recv()`, `mg_tls_pending()`, `mg_tls_handshake()`

**Impact**: Production-ready TLS configuration

#### 11. File System Abstraction

**Why**: Custom file backends, embedded systems

- `mg_fs_open()`, `mg_fs_close()`, `mg_fs_ls()`
- `mg_file_read()`, `mg_file_write()`, `mg_file_printf()`
- `mg_unpacked()` - Access packed resources

**Impact**: Niche use cases, custom FS backends

#### 12. RPC Framework

**Why**: Built-in RPC over HTTP

- `mg_rpc_add()`, `mg_rpc_del()`, `mg_rpc_process()`
- `mg_rpc_ok()`, `mg_rpc_err()`, `mg_rpc_req()`
- `mg_rpc_list()` - List registered methods

**Impact**: Rapid RPC server development

#### 13. Cryptography Primitives

**Why**: Low-level, mostly used internally by TLS

- **Base64**: `mg_base64_encode()`, `mg_base64_decode()`
- **Hashing**: `mg_md5_*`, `mg_sha1_*`, `mg_sha256_*`, `mg_sha384_*`
- **HMAC**: `mg_hmac_sha256()`
- **ECC/RSA**: `mg_uecc_*`, `mg_rsa_*` (very low-level)

**Impact**: Useful for auth, signing (stdlib alternatives exist)

#### 14. Embedded/IoT Features

**Why**: Python rarely runs on embedded hardware

- **TCP/IP stack**: `mg_tcpip_*` - Bare-metal TCP/IP
- **WiFi**: `mg_wifi_connect()`, `mg_wifi_scan()`, etc.
- **OTA updates**: `mg_ota_*`
- **Flash**: `mg_flash_*`
- **SDIO**: `mg_sdio_*`

**Impact**: Not relevant for Python use cases

#### 15. Advanced Connection Management

**Why**: Low-level, manual connection setup

- `mg_wrapfd()` - Wrap existing file descriptor
- `mg_alloc_conn()`, `mg_open_listener()` - Manual connection creation
- `mg_connect_svc()` - Connection with service-specific params
- `mg_connect_resolved()` - Connect with pre-resolved address

**Impact**: Power users, special connection handling

## Implementation Roadmap

### Immediate (Next PR)

1. **JSON parsing** (`mg_json_*`) - Enables modern API development
2. **Connection addresses** (`mg_addr` exposure) - Essential for logging, ACL, diagnostics
3. **HTTP serve_file** (`mg_http_serve_file`) - Complement to serve_dir
4. **Wakeup** (`mg_wakeup`) - Critical for thread-safe async patterns

### Short Term (2-3 PRs)

1. **MQTT basic support** - connect/listen/pub/sub (huge use case for Python)
2. **Multipart forms** (`mg_http_next_multipart`) - File uploads
3. **URL encoding** (`mg_url_encode`) - Complete URL utilities
4. **Timer API** (`mg_timer_add`) - Periodic tasks without threads
5. **HTTP status/header parsing** (`mg_http_status`, `mg_http_get_header_var`)

### Medium Term (Future releases)

1. **DNS resolution** (`mg_resolve`) - Async DNS
2. **SNTP** - Time synchronization
3. **RPC framework** - Built-in RPC server
4. **TLS configuration** - Production TLS support
5. **Base64/hashing utilities** - Common crypto needs

### Long Term (As needed)

1. Advanced connection management
2. File system abstraction
3. Low-level crypto (ECC, RSA)

## Prioritization Criteria

Features are prioritized based on:

1. **Usage frequency** - HTTP/JSON >> MQTT >> DNS >> embedded features
2. **Production readiness** - Error handling, diagnostics, TLS
3. **Architectural completeness** - Missing pieces that block common patterns (wakeup, timers)
4. **Python relevance** - Avoid bare-metal features (TCP/IP stack, WiFi)
5. **Stdlib alternatives** - Deprioritize if Python stdlib has good alternatives (some crypto)

## Notes

- Many low-level functions (`mg_call`, `mg_io_send`, `mg_io_recv`) are internal and shouldn't be exposed
- Some utilities (`mg_random`, `mg_bzero`, `mg_calloc`) have Python equivalents
- Embedded features (WiFi, OTA, Flash) are irrelevant for Python
- Crypto primitives might be useful but compete with `hashlib`, `base64` stdlib modules
