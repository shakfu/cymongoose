# Utility Functions

cymongoose provides utility functions for JSON parsing, URL parsing, pattern matching, hashing, encoding, and more.

## JSON Utilities

Mongoose includes a lightweight JSON parser. These functions extract values from JSON without full parsing.

### json_get

::: cymongoose.json_get
    options:
      members: true

Example:

```python
json_str = '{"user": {"name": "Alice", "age": 30}, "items": [1, 2, 3]}'

# Get nested value
name = json_get(json_str, "$.user.name")  # "Alice"

# Get array element
first = json_get(json_str, "$.items[0]")  # "1"
```

### json_get_num

::: cymongoose.json_get_num
    options:
      members: true

Example:

```python
json_str = '{"temperature": 23.5, "humidity": 65}'

temp = json_get_num(json_str, "$.temperature")  # 23.5
pressure = json_get_num(json_str, "$.pressure", default=0.0)  # 0.0
```

### json_get_bool

::: cymongoose.json_get_bool
    options:
      members: true

Example:

```python
json_str = '{"enabled": true, "debug": false}'

enabled = json_get_bool(json_str, "$.enabled")  # True
debug = json_get_bool(json_str, "$.debug")  # False
missing = json_get_bool(json_str, "$.other", default=False)  # False
```

### json_get_long

::: cymongoose.json_get_long
    options:
      members: true

Example:

```python
json_str = '{"count": 12345, "id": 9876543210}'

count = json_get_long(json_str, "$.count")  # 12345
user_id = json_get_long(json_str, "$.id")  # 9876543210
missing = json_get_long(json_str, "$.other", default=0)  # 0
```

### json_get_str

::: cymongoose.json_get_str
    options:
      members: true

Example:

```python
json_str = '{"message": "Hello, World!", "path": "/home/user"}'

# Automatically unescapes JSON strings
message = json_get_str(json_str, "$.message")  # "Hello, World!"
path = json_get_str(json_str, "$.path")  # "/home/user"
```

### Complete JSON Parsing Example

```python
from cymongoose import (
    json_get,
    json_get_num,
    json_get_bool,
    json_get_long,
    json_get_str,
)

def handler(conn, ev, data):
    if ev == MG_EV_HTTP_MSG:
        json_body = data.body_text

        # Parse different types
        user_id = json_get_long(json_body, "$.user.id")
        username = json_get_str(json_body, "$.user.name")
        age = json_get_num(json_body, "$.user.age")
        active = json_get_bool(json_body, "$.user.active")

        # Build response
        response = {
            "id": user_id,
            "name": username,
            "age": age,
            "active": active,
        }

        import json
        conn.reply(200, json.dumps(response).encode())
```

## URL Encoding and Parsing

### url_encode

::: cymongoose.url_encode
    options:
      members: true

Example:

```python
# Encode query parameters
param = url_encode("hello world")  # "hello%20world"
email = url_encode("user@example.com")  # "user%40example.com"

# Build query string
query = f"name={url_encode(name)}&email={url_encode(email)}"

# Make request
url = f"http://example.com/api?{query}"
conn = manager.connect(url, http=True)
```

### url_port

::: cymongoose.url_port
    options:
      members: true

### url_host

::: cymongoose.url_host
    options:
      members: true

### url_user

::: cymongoose.url_user
    options:
      members: true

### url_pass

::: cymongoose.url_pass
    options:
      members: true

### url_uri

::: cymongoose.url_uri
    options:
      members: true

### url_is_ssl

::: cymongoose.url_is_ssl
    options:
      members: true

Example:

```python
from cymongoose import url_port, url_host, url_user, url_pass, url_uri, url_is_ssl

url = "https://admin:secret@example.com:8443/api/v1?key=abc"

url_host(url)    # "example.com"
url_port(url)    # 8443
url_user(url)    # "admin"
url_pass(url)    # "secret"
url_uri(url)     # "/api/v1?key=abc"
url_is_ssl(url)  # True

# Default ports
url_port("http://example.com")   # 80
url_port("https://example.com")  # 443
url_port("mqtt://broker.com")    # 1883
```

## HTTP Variable Extraction

### http_var

::: cymongoose.http_var
    options:
      members: true

Example:

```python
from cymongoose import http_var

# Extract from query string
http_var("name=Alice&age=30", "name")  # "Alice"
http_var("name=Alice&age=30", "age")   # "30"
http_var("name=Alice", "missing")      # None

# In an HTTP handler, pass the query or body directly
def handler(conn, ev, data):
    if ev == MG_EV_HTTP_MSG:
        user = http_var(data.query, "user")
```

## Pattern Matching

### match

::: cymongoose.match
    options:
      members: true

Pattern syntax:

- `?` matches any single character (captures it)
- `*` matches zero or more characters except `/` (captures them)
- `#` matches zero or more characters including `/` (captures them)

Example:

```python
from cymongoose import match

# Exact match
match("hello", "hello")          # (True, [])

# Wildcard captures
match("/api/users", "/api/*")    # (True, ["users"])
match("/a/b/c", "#")             # (True, ["/a/b/c"])

# Route matching with multiple captures
match("/users/42", "/users/??"  )  # (True, ["4", "2"])
match("/api/v1/items", "/api/*/items")  # (True, ["v1"])

# No match
match("foo/bar", "*")            # (False, []) -- * doesn't cross /
```

## JSON-RPC Framework

### Rpc

::: cymongoose.Rpc
    options:
      members: true
      member-order: bysource

### RpcReq

::: cymongoose.RpcReq
    options:
      members: true
      member-order: bysource

Example:

```python
import json
from cymongoose import Rpc, RpcReq, json_get_num, json_get_str, MG_EV_HTTP_MSG

rpc = Rpc()

def add(req):
    a = json_get_num(req.frame, "$.params[0]")
    b = json_get_num(req.frame, "$.params[1]")
    req.ok(str(a + b))

def greet(req):
    name = json_get_str(req.frame, "$.params[0]")
    req.ok(json.dumps(f"Hello, {name}!"))

def fail(req):
    req.err(-32000, "something went wrong")

rpc.add("add", add)
rpc.add("greet", greet)
rpc.add("fail", fail)

print(rpc.methods)  # ["fail", "greet", "add"]

def handler(conn, ev, data):
    if ev == MG_EV_HTTP_MSG and data.uri == "/rpc":
        response = rpc.process(data.body_text)
        conn.reply(200, response, {"Content-Type": "application/json"})
        conn.drain()
```

## Hashing

### md5

::: cymongoose.md5
    options:
      members: true

### sha1

::: cymongoose.sha1
    options:
      members: true

### sha256

::: cymongoose.sha256
    options:
      members: true

### hmac_sha256

::: cymongoose.hmac_sha256
    options:
      members: true

Example:

```python
from cymongoose import md5, sha1, sha256, hmac_sha256

# Hash data (accepts str or bytes)
md5("hello")           # 16-byte digest
sha1("hello")          # 20-byte digest
sha256("hello")        # 32-byte digest

# HMAC for message authentication
sig = hmac_sha256("secret-key", "message-to-sign")

# Hex representation
sha256(b"hello").hex()  # "2cf24dba5fb0a30e..."
```

## Base64

### base64_encode

::: cymongoose.base64_encode
    options:
      members: true

### base64_decode

::: cymongoose.base64_decode
    options:
      members: true

Example:

```python
from cymongoose import base64_encode, base64_decode

encoded = base64_encode(b"Hello, World!")  # "SGVsbG8sIFdvcmxkIQ=="
decoded = base64_decode(encoded)            # b"Hello, World!"

# Works with str input too
base64_encode("binary data")
```

## Misc Utilities

### millis

::: cymongoose.millis
    options:
      members: true

### random_bytes

::: cymongoose.random_bytes
    options:
      members: true

### random_str

::: cymongoose.random_str
    options:
      members: true

### crc32

::: cymongoose.crc32
    options:
      members: true

Example:

```python
from cymongoose import millis, random_bytes, random_str, crc32

# Monotonic time
start = millis()
# ... do work ...
elapsed = millis() - start

# Random data
token = random_str(32)       # e.g. "aB3kM9xQ..."
nonce = random_bytes(16)     # 16 random bytes

# CRC32 checksum
checksum = crc32(b"hello")
# Incremental
crc = crc32(b"hel")
crc = crc32(b"lo", crc)     # same as crc32(b"hello")
```

## Multipart Form Data

### http_parse_multipart

::: cymongoose.http_parse_multipart
    options:
      members: true

Example:

```python
from cymongoose import MG_EV_HTTP_MSG, http_parse_multipart

def handler(conn, ev, data):
    if ev == MG_EV_HTTP_MSG and data.method == "POST":
        # Parse multipart form data
        offset = 0
        while True:
            offset, part = http_parse_multipart(data.body_bytes, offset)
            if part is None:
                break  # No more parts

            # Field name
            field_name = part['name']

            # File upload
            if part['filename']:
                filename = part['filename']
                file_data = part['body']
                print(f"File upload: {filename} ({len(file_data)} bytes)")

                # Save file
                with open(f"uploads/{filename}", "wb") as f:
                    f.write(file_data)
            else:
                # Regular form field
                field_value = part['body'].decode('utf-8')
                print(f"Field: {field_name} = {field_value}")

        conn.reply(200, b'{"status": "uploaded"}')
        conn.drain()
```

### File Upload Server Example

```python
import os
from cymongoose import Manager, MG_EV_HTTP_MSG, http_parse_multipart

def handler(conn, ev, data):
    if ev == MG_EV_HTTP_MSG:
        if data.method == "POST" and data.uri == "/upload":
            os.makedirs("uploads", exist_ok=True)

            offset = 0
            uploaded_files = []

            while True:
                offset, part = http_parse_multipart(data.body_bytes, offset)
                if part is None:
                    break

                if part['filename']:
                    # Save uploaded file
                    filename = part['filename']
                    filepath = os.path.join("uploads", filename)

                    with open(filepath, "wb") as f:
                        f.write(part['body'])

                    uploaded_files.append(filename)
                    print(f"Saved: {filepath}")

            # Return success response
            import json
            response = {
                "status": "success",
                "files": uploaded_files,
            }
            conn.reply(200, json.dumps(response).encode(),
                      headers={"Content-Type": "application/json"})
        else:
            # Serve upload form
            html = b"""
            <html>
            <body>
                <h1>File Upload</h1>
                <form method="POST" action="/upload"
                      enctype="multipart/form-data">
                    <input type="file" name="files" multiple>
                    <button type="submit">Upload</button>
                </form>
            </body>
            </html>
            """
            conn.reply(200, html,
                      headers={"Content-Type": "text/html"})
        conn.drain()
```

## Event Debugging

### event_name

::: cymongoose.event_name
    options:
      members: true

Example:

```python
from cymongoose import event_name, MG_EV_HTTP_MSG

def handler(conn, ev, data):
    print(f"Event: {event_name(ev)}")  # "MG_EV_HTTP_MSG"
```

## Logging Control

Control the Mongoose C library's internal logging.

### log_set

::: cymongoose.log_set
    options:
      members: true

### log_get

::: cymongoose.log_get
    options:
      members: true

Example:

```python
from cymongoose import log_set, log_get, MG_LL_DEBUG, MG_LL_NONE

# Enable debug logging
log_set(MG_LL_DEBUG)

# Check current level
print(log_get())  # 3

# Disable logging
log_set(MG_LL_NONE)
```

## Constants

### Event Types

See [Guide](../guide/index.md) for event handling details.

```python
from cymongoose import (
    MG_EV_ERROR,
    MG_EV_OPEN,
    MG_EV_POLL,
    MG_EV_RESOLVE,
    MG_EV_CONNECT,
    MG_EV_ACCEPT,
    MG_EV_TLS_HS,
    MG_EV_READ,
    MG_EV_WRITE,
    MG_EV_CLOSE,
    MG_EV_HTTP_HDRS,
    MG_EV_HTTP_MSG,
    MG_EV_WS_OPEN,
    MG_EV_WS_MSG,
    MG_EV_WS_CTL,
    MG_EV_MQTT_CMD,
    MG_EV_MQTT_MSG,
    MG_EV_MQTT_OPEN,
    MG_EV_SNTP_TIME,
    MG_EV_WAKEUP,
    MG_EV_USER,
)
```

### MQTT v5 Property Types

```python
from cymongoose import (
    MQTT_PROP_TYPE_BYTE,
    MQTT_PROP_TYPE_SHORT,
    MQTT_PROP_TYPE_INT,
    MQTT_PROP_TYPE_VARIABLE_INT,
    MQTT_PROP_TYPE_STRING,
    MQTT_PROP_TYPE_STRING_PAIR,
    MQTT_PROP_TYPE_BINARY_DATA,
)
```

### WebSocket Opcodes

```python
from cymongoose import (
    WEBSOCKET_OP_TEXT,
    WEBSOCKET_OP_BINARY,
    WEBSOCKET_OP_PING,
    WEBSOCKET_OP_PONG,
)

# Use with ws_send()
conn.ws_send("Hello", WEBSOCKET_OP_TEXT)
conn.ws_send(b"\x00\x01\x02", WEBSOCKET_OP_BINARY)
```

## See Also

- `HttpMessage` - HTTP message access
- `Connection` - Connection methods
- [Examples](../examples.md) - Complete examples
