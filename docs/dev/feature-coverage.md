# Mongoose API Coverage

Living document tracking which parts of the mongoose C API are exposed in
cymongoose and which are intentionally excluded. Update on each upstream
upgrade.

Last reviewed against: **mongoose 7.21**

## Wrapped

- **Core event loop**: `mg_mgr_init/poll/free`, `mg_listen`, `mg_connect`, `mg_send`, `mg_printf`, `mg_close_conn`, `mg_error`
- **HTTP** (client + server): `mg_http_listen`, `mg_http_connect`, `mg_http_reply`, `mg_http_serve_dir`, `mg_http_serve_file`, `mg_http_get_header`, `mg_http_get_var`, `mg_http_var`, `mg_http_parse`, `mg_http_get_request_len`, `mg_http_printf_chunk`, `mg_http_write_chunk`, `mg_http_creds`, `mg_http_bauth`, `mg_http_upload`, `mg_http_next_multipart`, `mg_http_serve_ssi`, `mg_http_get_header_var`, `mg_http_status`
- **WebSocket**: `mg_ws_connect`, `mg_ws_upgrade`, `mg_ws_send`, `mg_ws_printf`, `mg_ws_wrap`
- **MQTT**: `mg_mqtt_connect`, `mg_mqtt_listen`, `mg_mqtt_login`, `mg_mqtt_pub`, `mg_mqtt_sub`, `mg_mqtt_unsub`, `mg_mqtt_ping`, `mg_mqtt_pong`, `mg_mqtt_disconnect`
- **MQTT v5 properties**: `mg_mqtt_next_prop`, `mg_mqtt_prop` struct, `MQTT_PROP_TYPE_*` constants
- **TLS**: `mg_tls_init`, `mg_tls_free`
- **SNTP**: `mg_sntp_connect`, `mg_sntp_request`, `mg_sntp_parse`
- **JSON parsing**: `mg_json_get`, `mg_json_get_tok`, `mg_json_get_num`, `mg_json_get_bool`, `mg_json_get_long`, `mg_json_get_str`, `mg_json_get_hex`, `mg_json_get_b64`, `mg_json_unescape`, `mg_json_next`
- **RPC**: `mg_rpc_add`, `mg_rpc_del`, `mg_rpc_process`, `mg_rpc_ok`, `mg_rpc_err`, `mg_rpc_list`
- **Timers**: `mg_timer_add`, `mg_timer_free`
- **Wakeup**: `mg_wakeup`, `mg_wakeup_init`
- **URL parsing**: `mg_url_encode`, `mg_url_port`, `mg_url_host`, `mg_url_user`, `mg_url_pass`, `mg_url_uri`, `mg_url_is_ssl`
- **Pattern matching**: `mg_match`
- **DNS resolution**: `mg_resolve`, `mg_resolve_cancel`
- **Hashing**: `mg_md5_init/update/final`, `mg_sha1_init/update/final`, `mg_sha256`, `mg_hmac_sha256`
- **Base64**: `mg_base64_encode`, `mg_base64_decode`
- **Utilities**: `mg_str_n`, `mg_free`, `mg_millis`, `mg_random`, `mg_random_str`, `mg_crc32`

## Not wrapped

| Subsystem | What's there | Why skip |
|---|---|---|
| **String comparison** | `mg_casecmp`, `mg_strcmp`, `mg_span`, `mg_strdup`, `mg_str_to_num` | Python string ops are sufficient |
| **Filesystem** | `mg_fs`, `mg_fd`, `mg_file_read/write`, packed FS (`mg_unpack`/`mg_unlist`) | Embedded-oriented VFS; Python has `os`/`pathlib` |
| **TCP/IP stack** | `mg_tcpip_*`, all driver structs, PHY, SDIO, WiFi | Bare-metal network stack for MCUs; irrelevant on a host OS |
| **WiFi** | `mg_wifi_connect/disconnect/scan/ap_start/ap_stop` | MCU WiFi management |
| **OTA** | `mg_ota_begin/write/end`, `mg_flash` | Firmware update; embedded only |
| **mDNS/DNS-SD** | `mg_mdns_listen`, `mg_mdns_query`, `mg_dnssd_record` | Events are declared but the full mDNS API is niche |
| **Crypto internals** | All `mg_uecc_*`, `mg_tls_x25519`, `mg_aes_gcm_*`, `mg_rsa_*` | TLS implementation internals; Python has `ssl`/`cryptography` |
| **Low-level I/O** | `mg_iobuf_*`, `mg_queue_*`, `mg_io_send/recv`, `mg_pfn_*` | Internal plumbing (some used internally by the RPC wrapper) |
| **Printing** | `mg_xprintf`, `mg_snprintf`, `mg_print_ip`, `mg_print_mac`, etc. | C formatting helpers; no value from Python |
| **DNS internals** | `mg_dns_parse`, `mg_dns_parse_rr`, header/RR structs | `mg_resolve` is already wrapped; raw DNS parsing is niche |
| **TLS internals** | `mg_tls_send/recv/pending/flush/handshake`, `mg_tls_ctx_*` | Internal to the TLS state machine |
| **Connection internals** | `mg_alloc_conn`, `mg_open_listener`, `mg_wrapfd`, `mg_connect_resolved` | Low-level connection setup |

## Exclusion rationale

Everything above falls into one of three categories:

1. **Embedded-platform-specific** (TCP/IP stack, WiFi, OTA, filesystem) -- irrelevant on a host OS where Python runs.
2. **Internal plumbing** (iobuf, queue, print callbacks, TLS state machine, connection internals) -- implementation details not useful from Python. Some are used internally by the binding itself (e.g. `mg_pfn_iobuf` backs the RPC wrapper).
3. **Redundant with Python stdlib** (string comparison, DNS record parsing) -- Python's built-in equivalents are more ergonomic.
