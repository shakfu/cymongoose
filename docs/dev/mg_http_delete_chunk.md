# mg_http_delete_chunk - Missing Function

## Status

**NOT IMPLEMENTED** - This function is declared in `mongoose.h` but not implemented in `mongoose.c`.

## Declaration

```c
void mg_http_delete_chunk(struct mg_connection *c, struct mg_http_message *hm);
```

## Issue

The Mongoose library (as vendored in `thirdparty/mongoose/`) contains a forward declaration for `mg_http_delete_chunk` in the header file, but the function is not implemented in the source code. Attempting to link against this function results in:

```text
symbol not found in flat namespace '_mg_http_delete_chunk'
```

This appears to be a planned feature that was either:

- Never implemented in this version of Mongoose
- Removed in a refactoring
- Only available in certain Mongoose builds/configurations

## Intended Purpose

Based on the function signature and context, `mg_http_delete_chunk` was intended to **remove processed chunked data from the receive buffer** when handling incoming HTTP requests with `Transfer-Encoding: chunked`.

### Use Case

When a server receives chunked HTTP requests (client-to-server streaming):

1. Client sends data in chunks with `Transfer-Encoding: chunked`
2. Server processes each chunk as it arrives
3. `mg_http_delete_chunk` would delete processed chunks from the buffer
4. This prevents memory accumulation on large uploads

### Example (Hypothetical)

```python
def handler(conn, ev, data):
    if ev == MG_EV_HTTP_MSG:
        # Process chunk
        process_chunk(data.body_bytes)

        # Delete processed chunk from receive buffer
        conn.http_delete_chunk(data)  # NOT AVAILABLE
```

## Practical Impact

### Severity: Low to Medium

The absence of this function has **limited practical impact** for most use cases:

### [x] No Impact - Normal HTTP Operations

- **Regular HTTP requests**: Fully buffered before `MG_EV_HTTP_MSG` fires - no issue
- **HTTP responses**: Chunked sending works perfectly via `Connection.http_chunk()`
- **Small to medium uploads**: Mongoose buffers automatically, no memory issues
- **WebSocket/MQTT**: Use different protocols, not affected

### [!] Medium Impact - Large Chunked Uploads

- **Very large chunked requests**: Entire request accumulates in memory
- **Streaming request processing**: Cannot process and discard chunks incrementally
- **Memory-constrained environments**: Could cause memory pressure with large uploads

### Affected Scenarios

1. **Large file uploads with chunked encoding**:
   - Without `mg_http_delete_chunk`, the entire upload stays in memory
   - Workaround: Use `Content-Length` based uploads or multipart forms

2. **Long-running streaming requests**:
   - Cannot incrementally process and clear chunks
   - Workaround: Use WebSocket for streaming data

3. **Memory-limited embedded systems**:
   - Risk of buffer exhaustion on large chunked requests
   - Workaround: Implement request size limits, reject chunked encoding

## Workarounds

Since `mg_http_delete_chunk` is not available, consider these alternatives:

### 1. Use Content-Length Based Uploads

```python
def handler(conn, ev, data):
    if ev == MG_EV_HTTP_MSG:
        # Check Content-Length header
        content_length = data.header("Content-Length")
        if content_length and int(content_length) > MAX_SIZE:
            conn.reply(413, b"Payload Too Large")
            return

        # Process complete buffered request
        process_upload(data.body_bytes)
        conn.reply(200, b"OK")
```

### 2. Monitor Buffer Size for Backpressure

```python
def handler(conn, ev, data):
    if ev == MG_EV_READ:
        # Check receive buffer size
        if conn.recv_len > MAX_BUFFER_SIZE:
            conn.error("Buffer overflow - request too large")
            conn.close()
            return
```

### 3. Use Multipart Form Uploads

```python
from cymongoose import http_parse_multipart

def handler(conn, ev, data):
    if ev == MG_EV_HTTP_MSG:
        # Parse multipart with size limit
        offset = 0
        while True:
            offset, part = http_parse_multipart(data.body_bytes, offset)
            if offset == 0:
                break

            # Process each part incrementally
            process_part(part)

        conn.reply(200, b"Upload complete")
```

### 4. Use WebSocket for Streaming

```python
def handler(conn, ev, data):
    if ev == MG_EV_WS_MSG:
        # Process WebSocket frames incrementally
        # Each frame is automatically cleared after processing
        process_data(data.data)
```

### 5. Implement Request Size Limits

```python
MAX_REQUEST_SIZE = 10 * 1024 * 1024  # 10MB

def handler(conn, ev, data):
    if ev == MG_EV_HTTP_MSG:
        if len(data.body_bytes) > MAX_REQUEST_SIZE:
            conn.reply(413, b"Payload Too Large")
            return

        process_request(data.body_bytes)
        conn.reply(200, b"OK")
```

## Buffer Management

While `mg_http_delete_chunk` is unavailable, you can still monitor buffer state:

```python
def handler(conn, ev, data):
    if ev == MG_EV_READ:
        # Monitor receive buffer
        print(f"Receive buffer: {conn.recv_len}/{conn.recv_size} bytes")

        # Check for backpressure
        if conn.is_full:
            print("Warning: Receive buffer is full")
```

## Recommendations

### For Application Developers

1. **Prefer Content-Length over chunked encoding** for uploads
2. **Implement size limits** on all incoming requests
3. **Use WebSocket** for true streaming scenarios
4. **Monitor buffer usage** with `conn.recv_len` and `conn.is_full`
5. **Handle backpressure** appropriately in high-volume scenarios

### For cymongoose Maintainers

1. **Do not implement a stub** - the function doesn't exist in Mongoose
2. **Document this limitation** clearly (this file)
3. **Track upstream** - monitor Mongoose project for implementation
4. **Consider contributing** upstream to add this feature to Mongoose

## Upstream Status

This is an **upstream Mongoose issue**, not a cymongoose wrapper issue.

### Potential Actions

1. **File issue with Mongoose project**: Request implementation or clarification
2. **Contribute implementation**: If needed, implement and submit PR to Mongoose
3. **Remove declaration**: Suggest removing the forward declaration if not planned

### Related Mongoose Functions

Available alternatives in Mongoose/cymongoose:

- `mg_http_write_chunk()` [x] - Send chunked responses (implemented)
- `mg_http_printf_chunk()` [x] - Send formatted chunks (declared, not wrapped)
- `conn.recv_data()` [x] - Read receive buffer (cymongoose extension)
- `conn.recv_len` [x] - Check buffer size (cymongoose extension)
- `conn.is_full` [x] - Check backpressure (cymongoose extension)

## Conclusion

The absence of `mg_http_delete_chunk` is a **known limitation** of the underlying Mongoose library. For most HTTP use cases, this has minimal impact. For scenarios requiring incremental processing of large chunked uploads:

- Use **alternative upload mechanisms** (Content-Length, multipart)
- Use **WebSocket** for streaming data
- Implement **size limits** and **backpressure handling**

This limitation should be tracked upstream with the Mongoose project, as it affects all Mongoose users, not just cymongoose.

## References

- Mongoose header declaration: `thirdparty/mongoose/mongoose.h:142`
- Missing implementation: `thirdparty/mongoose/mongoose.c` (search returns no results)
- Related issue: [Link to GitHub issue when created]
- Mongoose project: <https://github.com/cesanta/mongoose>
