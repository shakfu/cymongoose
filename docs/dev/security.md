# Security Considerations

This document outlines security considerations when using cymongoose for network applications.

## HTTP Basic Authentication

### Overview

The `Connection.http_basic_auth()` method implements HTTP Basic Authentication (RFC 7617), which transmits credentials encoded in Base64 format.

### Security Model

- **Base64 is encoding, not encryption** - credentials can be trivially decoded by anyone who intercepts them
- **Safe over HTTPS/TLS** - the TLS layer encrypts all traffic including the Authorization header
- **Unsafe over HTTP** - credentials are transmitted in plaintext and visible to network observers

### Recommended Usage

[x] **SAFE - Always use HTTPS for authentication:**

```python
# Credentials are encrypted by TLS
conn = manager.connect("https://api.example.com/", http=True)
conn.http_basic_auth("username", "password")
```

[X] **UNSAFE - Never send credentials over HTTP:**

```python
# Credentials visible to anyone monitoring the network
conn = manager.connect("http://api.example.com/", http=True)
conn.http_basic_auth("username", "password")  # DANGEROUS
```

### Alternative Authentication Methods

For production applications, consider:

- **Token-based auth** - OAuth 2.0, JWT tokens
- **API keys** - In headers (still requires HTTPS)
- **Mutual TLS** - Certificate-based authentication
- **Custom authentication** - Application-specific protocols

## TLS/HTTPS Security

### Certificate Verification

When using TLS connections, Mongoose validates server certificates by default. To configure:

```python
# Future: TLS configuration will be exposed via mg_tls_opts
# For now, certificate validation is handled by Mongoose internally
```

**Note:** TLS configuration (`mg_tls_opts`) is not yet wrapped in cymongoose. When implemented:

- Always validate certificates in production (`skip_verification=False`)
- Only skip verification for development/testing with trusted local servers

## Connection Security

### Transport Encryption

- **TCP/HTTP** - No encryption, all data visible on network
- **TLS/HTTPS/WSS** - Encrypted transport, protects data in transit
- **UDP** - No built-in encryption

### Recommendations

1. **Use TLS for sensitive data** - Always encrypt connections carrying credentials, personal data, or confidential information
2. **Validate inputs** - Sanitize all data received from network connections
3. **Rate limiting** - Use connection flow control (`is_full`, `is_draining`) to prevent resource exhaustion
4. **Authentication** - Verify client identity for sensitive operations

## Error Handling

### Information Disclosure

The `Connection.error()` method triggers error events with error messages. Be careful not to expose sensitive information:

```python
# [X] BAD - Exposes internal paths/details
conn.error(f"Database connection failed: {db_password}")

# [x] GOOD - Generic error message
conn.error("Authentication failed")
```

### Error Event Data

Error events (`MG_EV_ERROR`) may contain:

- Network error details
- Connection state information
- Protocol-specific error messages

**Recommendation:** Log detailed errors server-side, but send generic messages to clients.

## DNS Resolution

### DNS Spoofing

The `Connection.resolve()` method performs DNS lookups which are vulnerable to:

- **DNS cache poisoning**
- **Man-in-the-middle attacks**
- **DNS rebinding attacks**

### Mitigations

1. **Use DNSSEC** - When available, provides cryptographic validation
2. **Validate resolved addresses** - Check resolved IPs against expected ranges
3. **Use TLS** - Even if DNS is spoofed, TLS certificate validation prevents connection to wrong server

```python
def handler(conn, ev, data):
    if ev == MG_EV_RESOLVE:
        # Validate resolved address before connecting
        addr = conn.remote_addr
        if not is_valid_address(addr):
            conn.close()
            return
```

## WebSocket Security

### Origin Validation

WebSocket connections can be initiated from any origin. Always validate:

```python
def ws_handler(conn, ev, data):
    if ev == MG_EV_HTTP_MSG:  # WebSocket upgrade request
        origin = data.header("Origin")
        if not is_allowed_origin(origin):
            conn.reply(403, b"Forbidden")
            return
        # Proceed with upgrade
        conn.ws_upgrade(data)
```

### WSS (WebSocket Secure)

- Always use `wss://` (WebSocket over TLS) for sensitive data
- Never use `ws://` for authentication tokens or personal information

## MQTT Security

### MQTT Authentication

MQTT supports username/password authentication:

```python
# Credentials sent in CONNECT packet
conn = manager.mqtt_connect(
    "mqtt://broker.example.com:1883",
    username="user",
    password="pass"  # Transmitted in cleartext over TCP!
)
```

**Security Considerations:**

1. **Use MQTT over TLS** - Use `mqtts://` or port 8883 for encrypted transport
2. **Strong passwords** - MQTT passwords are often stored in plaintext on broker
3. **Client ID randomization** - Prevent client ID spoofing

```python
# [x] SECURE - MQTT over TLS
conn = manager.mqtt_connect(
    "mqtts://broker.example.com:8883",
    client_id=generate_random_id(),
    username="user",
    password="pass"
)
```

## Input Validation

### HTTP Request Parsing

Always validate and sanitize inputs from HTTP requests:

```python
def handler(conn, ev, data):
    if ev == MG_EV_HTTP_MSG:
        # Validate URI
        if len(data.uri) > 2048:
            conn.reply(414, b"URI Too Long")
            return

        # Validate headers
        content_length = data.header("Content-Length")
        if content_length and int(content_length) > MAX_BODY_SIZE:
            conn.reply(413, b"Payload Too Large")
            return

        # Sanitize query parameters
        param = data.query_var("user_input")
        if param:
            param = sanitize(param)
```

### JSON Input

When parsing JSON with `json_get*` functions:

```python
# Validate JSON input size
if len(json_data) > MAX_JSON_SIZE:
    return error("JSON too large")

# Handle parsing errors
result = json_get(json_data, "$.user.email")
if result is None:
    return error("Invalid JSON structure")

# Validate extracted values
email = json_get_str(json_data, "$.email")
if email and not is_valid_email(email):
    return error("Invalid email format")
```

## Resource Management

### Connection Limits

Prevent resource exhaustion:

```python
# Track active connections
active_connections = 0
MAX_CONNECTIONS = 1000

def handler(conn, ev, data):
    global active_connections

    if ev == MG_EV_ACCEPT:
        active_connections += 1
        if active_connections > MAX_CONNECTIONS:
            conn.close()
            active_connections -= 1
            return

    elif ev == MG_EV_CLOSE:
        active_connections -= 1
```

### Flow Control

Use backpressure flags to prevent memory exhaustion:

```python
def handler(conn, ev, data):
    if ev == MG_EV_READ:
        if conn.is_full:
            # Connection buffer full, stop accepting data
            # Mongoose will automatically handle backpressure
            return
```

## Common Vulnerabilities

### Path Traversal

When serving files, validate paths:

```python
def handler(conn, ev, data):
    if ev == MG_EV_HTTP_MSG:
        # [X] DANGEROUS - Path traversal vulnerability
        file_path = data.uri  # Could be "../../../../etc/passwd"
        conn.serve_file(data, file_path)

        # [x] SAFE - Validate and sanitize path
        file_path = sanitize_path(data.uri)
        if not is_safe_path(file_path, ALLOWED_DIR):
            conn.reply(403, b"Forbidden")
            return
        conn.serve_file(data, file_path)
```

### Command Injection

Never pass unsanitized input to system commands:

```python
# [X] DANGEROUS
filename = data.query_var("file")
os.system(f"cat {filename}")  # Command injection!

# [x] SAFE - Validate and use safe APIs
filename = sanitize_filename(data.query_var("file"))
with open(filename, 'r') as f:
    content = f.read()
```

### Cross-Site Scripting (XSS)

Escape HTML output:

```python
# [X] DANGEROUS - XSS vulnerability
user_input = data.query_var("name")
conn.reply(200, f"<html>Hello {user_input}</html>")

# [x] SAFE - Escape HTML
import html
user_input = data.query_var("name")
safe_input = html.escape(user_input)
conn.reply(200, f"<html>Hello {safe_input}</html>")
```

## Security Checklist

### For Production Deployments

- [ ] Use HTTPS/TLS for all sensitive data transmission
- [ ] Validate server certificates (don't skip TLS verification)
- [ ] Implement proper authentication and authorization
- [ ] Validate and sanitize all user inputs
- [ ] Set connection and resource limits
- [ ] Implement rate limiting and backpressure handling
- [ ] Use secure WebSocket (WSS) and MQTT (MQTTS) connections
- [ ] Validate WebSocket origins
- [ ] Escape output to prevent XSS
- [ ] Prevent path traversal in file serving
- [ ] Log security events without exposing sensitive data
- [ ] Keep Mongoose library updated
- [ ] Review error messages for information disclosure
- [ ] Implement timeout mechanisms for all network operations

## Reporting Security Issues

If you discover a security vulnerability in cymongoose:

1. **Do not** open a public issue
2. Email security concerns to the maintainers
3. Include:
   - Description of the vulnerability
   - Steps to reproduce
   - Potential impact
   - Suggested fix (if available)

## References

- [HTTP Basic Authentication (RFC 7617)](https://tools.ietf.org/html/rfc7617)
- [TLS/SSL Best Practices](https://wiki.mozilla.org/Security/Server_Side_TLS)
- [OWASP Top 10](https://owasp.org/www-project-top-ten/)
- [WebSocket Security](https://datatracker.ietf.org/doc/html/rfc6455#section-10)
- [MQTT Security Fundamentals](http://docs.oasis-open.org/mqtt/mqtt/v3.1.1/os/mqtt-v3.1.1-os.html#_Toc398718127)
