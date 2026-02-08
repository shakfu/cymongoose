"""Type stubs for cymongoose._mongoose module.

This stub file provides type hints for the Cython extension module.
"""

from typing import Any, Callable, Dict, List, Optional, Tuple, Union

# Event constants
MG_EV_ERROR: int
MG_EV_OPEN: int
MG_EV_POLL: int
MG_EV_RESOLVE: int
MG_EV_CONNECT: int
MG_EV_ACCEPT: int
MG_EV_TLS_HS: int
MG_EV_READ: int
MG_EV_WRITE: int
MG_EV_CLOSE: int
MG_EV_HTTP_HDRS: int
MG_EV_HTTP_MSG: int
MG_EV_WS_OPEN: int
MG_EV_WS_MSG: int
MG_EV_WS_CTL: int
MG_EV_MQTT_CMD: int
MG_EV_MQTT_MSG: int
MG_EV_MQTT_OPEN: int
MG_EV_SNTP_TIME: int
MG_EV_WAKEUP: int
MG_EV_USER: int

# WebSocket opcodes
WEBSOCKET_OP_TEXT: int
WEBSOCKET_OP_BINARY: int
WEBSOCKET_OP_PING: int
WEBSOCKET_OP_PONG: int

# Log level constants
MG_LL_NONE: int
MG_LL_ERROR: int
MG_LL_INFO: int
MG_LL_DEBUG: int
MG_LL_VERBOSE: int

class HttpMessage:
    """Lightweight view over a struct mg_http_message."""

    @property
    def method(self) -> str:
        """HTTP method (GET, POST, etc.)."""
        ...

    @property
    def uri(self) -> str:
        """Request URI path."""
        ...

    @property
    def query(self) -> str:
        """Query string."""
        ...

    @property
    def proto(self) -> str:
        """HTTP protocol version (HTTP/1.1, etc.)."""
        ...

    @property
    def body_bytes(self) -> bytes:
        """Request/response body as bytes."""
        ...

    @property
    def body_text(self) -> str:
        """Request/response body as UTF-8 text."""
        ...

    def header(self, name: str, default: Optional[str] = None) -> Optional[str]:
        """Return a HTTP header value or default when not present.

        Args:
            name: Header name (case-insensitive)
            default: Default value if header not found

        Returns:
            Header value or default
        """
        ...

    def headers(self) -> List[Tuple[str, str]]:
        """Return all HTTP headers as a list of (name, value) tuples."""
        ...

    def query_var(self, name: str) -> Optional[str]:
        """Extract a query string parameter.

        Args:
            name: Parameter name

        Returns:
            Parameter value or None if not found

        Raises:
            ValueError: If decoded value exceeds 2048-byte buffer limit
        """
        ...

    def status(self) -> Optional[int]:
        """Return HTTP status code from response message.

        Returns:
            Status code (e.g., 200, 404) or None if not available
        """
        ...

    def header_var(self, header_name: str, var_name: str) -> Optional[str]:
        """Parse a variable from a header value.

        Useful for parsing sub-values like charset from Content-Type header.
        Example: header_var("Content-Type", "charset") -> "utf-8"

        Args:
            header_name: Name of the header (e.g., "Content-Type")
            var_name: Name of the variable to extract (e.g., "charset")

        Returns:
            The variable value or None if not found
        """
        ...

    def __bool__(self) -> bool: ...

class WsMessage:
    """View over an incoming WebSocket frame."""

    @property
    def data(self) -> bytes:
        """Frame data as bytes."""
        ...

    @property
    def text(self) -> str:
        """Frame data as UTF-8 text."""
        ...

    @property
    def flags(self) -> int:
        """WebSocket frame flags."""
        ...

class MqttMessage:
    """View over an incoming MQTT message."""

    @property
    def topic(self) -> str:
        """MQTT topic."""
        ...

    @property
    def data(self) -> bytes:
        """Message payload as bytes."""
        ...

    @property
    def text(self) -> str:
        """Message payload as UTF-8 text."""
        ...

    @property
    def id(self) -> int:
        """Message ID."""
        ...

    @property
    def cmd(self) -> int:
        """MQTT command type."""
        ...

    @property
    def qos(self) -> int:
        """Quality of Service level."""
        ...

    @property
    def ack(self) -> int:
        """Acknowledgement field."""
        ...

class TlsOpts:
    """TLS configuration options for secure connections.

    Used to configure TLS/SSL settings for HTTPS, WSS, MQTTS, etc.
    """

    ca: bytes
    cert: bytes
    key: bytes
    name: bytes
    skip_verification: bool

    def __init__(
        self,
        ca: Union[bytes, str, None] = None,
        cert: Union[bytes, str, None] = None,
        key: Union[bytes, str, None] = None,
        name: Union[bytes, str, None] = None,
        skip_verification: bool = False,
    ) -> None:
        """Initialize TLS options.

        Args:
            ca: CA certificate (PEM format) as bytes or str
            cert: Client certificate (PEM format) as bytes or str
            key: Private key (PEM format) as bytes or str
            name: Server name for SNI (Server Name Indication)
            skip_verification: Skip certificate verification (INSECURE - dev only!)

        Example:
            # Server with custom certificate
            opts = TlsOpts(
                cert=open('server.crt', 'rb').read(),
                key=open('server.key', 'rb').read()
            )

            # Client with custom CA
            opts = TlsOpts(
                ca=open('ca.crt', 'rb').read(),
                name='example.com'
            )

            # Development only - skip verification
            opts = TlsOpts(skip_verification=True)
        """
        ...

# Event handler type
EventHandler = Callable[["Connection", int, Any], None]

class Connection:
    """Wrapper around mg_connection pointers."""

    @property
    def handler(self) -> Optional[EventHandler]:
        """Per-connection event handler."""
        ...

    def set_handler(self, handler: Optional[EventHandler]) -> None:
        """Assign a per-connection event handler.

        Args:
            handler: Callable that takes (Connection, event, data)
        """
        ...

    @property
    def userdata(self) -> Any:
        """User-defined data attached to this connection."""
        ...

    @userdata.setter
    def userdata(self, value: Any) -> None: ...
    @property
    def id(self) -> int:
        """Return connection ID."""
        ...

    @property
    def is_listening(self) -> bool:
        """True if this is a listening connection."""
        ...

    @property
    def is_closing(self) -> bool:
        """True if connection is closing."""
        ...

    @property
    def local_addr(self) -> Optional[Tuple[str, int, bool]]:
        """Return local address as (ip, port, is_ipv6) tuple."""
        ...

    @property
    def remote_addr(self) -> Optional[Tuple[str, int, bool]]:
        """Return remote address as (ip, port, is_ipv6) tuple."""
        ...

    @property
    def is_client(self) -> bool:
        """Return True if this is a client connection."""
        ...

    @property
    def is_tls(self) -> bool:
        """Return True if this connection uses TLS."""
        ...

    @property
    def is_udp(self) -> bool:
        """Return True if this is a UDP connection."""
        ...

    @property
    def is_websocket(self) -> bool:
        """Return True if this is a WebSocket connection."""
        ...

    @property
    def is_readable(self) -> bool:
        """Return True if connection has data to read."""
        ...

    @property
    def is_writable(self) -> bool:
        """Return True if connection can be written to."""
        ...

    @property
    def is_full(self) -> bool:
        """Return True if receive buffer is full (backpressure - stop reads)."""
        ...

    @property
    def is_draining(self) -> bool:
        """Return True if connection is draining (sending remaining data before close)."""
        ...

    @property
    def recv_len(self) -> int:
        """Return number of bytes in receive buffer."""
        ...

    @property
    def send_len(self) -> int:
        """Return number of bytes in send buffer."""
        ...

    @property
    def recv_size(self) -> int:
        """Return total allocated size of receive buffer."""
        ...

    @property
    def send_size(self) -> int:
        """Return total allocated size of send buffer."""
        ...

    def send(self, data: Union[str, bytes]) -> None:
        """Send raw bytes to the peer.

        Args:
            data: Data to send (str will be UTF-8 encoded)

        Raises:
            RuntimeError: If send fails or connection is closed
        """
        ...

    def reply(
        self,
        status_code: int,
        body: Union[str, bytes] = b"",
        headers: Optional[Dict[str, str]] = None,
    ) -> None:
        """Send a HTTP reply (final response).

        Args:
            status_code: HTTP status code (e.g., 200, 404)
            body: Response body (str will be UTF-8 encoded)
            headers: Optional dict of headers
        """
        ...

    def serve_dir(
        self,
        message: HttpMessage,
        root_dir: str,
        extra_headers: str = "",
        mime_types: str = "",
        page404: str = "",
    ) -> None:
        """Serve files from a directory using Mongoose's built-in static handler.

        Args:
            message: HttpMessage from MG_EV_HTTP_MSG event
            root_dir: Root directory path
            extra_headers: Additional headers to include
            mime_types: Custom MIME type mappings
            page404: Custom 404 page path

        Raises:
            ValueError: If HttpMessage is not valid for this event
        """
        ...

    def serve_file(
        self, message: HttpMessage, path: str, extra_headers: str = "", mime_types: str = ""
    ) -> None:
        """Serve a single file using Mongoose's built-in static handler.

        Args:
            message: HttpMessage from MG_EV_HTTP_MSG event
            path: File path to serve
            extra_headers: Additional headers to include
            mime_types: Custom MIME type mappings

        Raises:
            ValueError: If HttpMessage is not valid for this event
        """
        ...

    def ws_upgrade(
        self, message: HttpMessage, extra_headers: Optional[Dict[str, str]] = None
    ) -> None:
        """Upgrade HTTP connection to WebSocket.

        Args:
            message: The HttpMessage from MG_EV_HTTP_MSG event
            extra_headers: Optional dict of extra headers to send in upgrade response

        Raises:
            ValueError: If HttpMessage is not valid for this event
        """
        ...

    def ws_send(self, data: Union[str, bytes], op: int = WEBSOCKET_OP_TEXT) -> None:
        """Send a WebSocket frame.

        Args:
            data: Frame data (str will be UTF-8 encoded)
            op: WebSocket opcode (default: WEBSOCKET_OP_TEXT)
        """
        ...

    def mqtt_pub(
        self, topic: str, message: Union[str, bytes], qos: int = 0, retain: bool = False
    ) -> int:
        """Publish an MQTT message.

        Args:
            topic: MQTT topic
            message: Message payload (str or bytes)
            qos: Quality of service (0, 1, or 2)
            retain: Retain flag

        Returns:
            Message ID
        """
        ...

    def mqtt_sub(self, topic: str, qos: int = 0) -> None:
        """Subscribe to an MQTT topic.

        Args:
            topic: MQTT topic (can include wildcards)
            qos: Quality of service (0, 1, or 2)
        """
        ...

    def mqtt_ping(self) -> None:
        """Send MQTT ping."""
        ...

    def mqtt_pong(self) -> None:
        """Send MQTT pong."""
        ...

    def mqtt_disconnect(self) -> None:
        """Send MQTT disconnect message.

        Gracefully disconnects from MQTT broker by sending a DISCONNECT packet.
        """
        ...

    def error(self, message: str) -> None:
        """Trigger an error event on this connection.

        Args:
            message: Error message
        """
        ...

    def recv_data(self, length: int = -1) -> bytes:
        """Read data from receive buffer without consuming it.

        Args:
            length: Number of bytes to read, or -1 for all

        Returns:
            Data from receive buffer
        """
        ...

    def send_data(self, length: int = -1) -> bytes:
        """Read data from send buffer without consuming it.

        Args:
            length: Number of bytes to read, or -1 for all

        Returns:
            Data from send buffer
        """
        ...

    def resolve(self, url: str) -> None:
        """Resolve a hostname asynchronously.

        Triggers MG_EV_RESOLVE event when DNS lookup completes.

        Args:
            url: URL to resolve (e.g., "google.com" or "tcp://example.com:80")
        """
        ...

    def resolve_cancel(self) -> None:
        """Cancel an ongoing DNS resolution."""
        ...

    def http_basic_auth(self, username: str, password: str) -> None:
        """Send HTTP Basic Authentication credentials.

        Typically used on client connections to authenticate with a server.

        Args:
            username: Username for basic auth
            password: Password for basic auth
        """
        ...

    def sntp_request(self) -> None:
        """Send an SNTP time request.

        Use on a connection created with Manager.sntp_connect().
        Triggers MG_EV_SNTP_TIME event when response is received.
        """
        ...

    def http_chunk(self, data: Union[str, bytes]) -> None:
        """Send an HTTP chunked transfer encoding chunk.

        Used for streaming HTTP responses. Must call with empty data to end.

        Args:
            data: Chunk data (str or bytes). Empty to signal end of chunks.

        Example:
            def handler(conn, ev, data):
                if ev == MG_EV_HTTP_MSG:
                    # Start chunked response
                    conn.reply(200, "", headers={"Transfer-Encoding": "chunked"})
                    conn.http_chunk("First chunk\\n")
                    conn.http_chunk("Second chunk\\n")
                    conn.http_chunk("")  # End chunks
        """
        ...

    def http_sse(self, event_type: str, data: str) -> None:
        """Send Server-Sent Events (SSE) formatted message.

        SSE is used for real-time server push over HTTP. Must start with appropriate headers.

        Args:
            event_type: Event type name (e.g., "message", "update")
            data: Event data payload

        Example:
            def handler(conn, ev, data):
                if ev == MG_EV_HTTP_MSG:
                    # Start SSE stream
                    conn.reply(200, "", headers={
                        "Content-Type": "text/event-stream",
                        "Cache-Control": "no-cache"
                    })
                    conn.http_sse("message", "Hello from server")
                    conn.http_sse("update", "Status: OK")
        """
        ...

    def close(self) -> None:
        """Immediately close the connection.

        For graceful shutdown, use drain() instead to let buffered data flush first.
        """
        ...

    def drain(self) -> None:
        """Mark connection for graceful closure.

        Sets is_draining=1, which tells Mongoose to:
        1. Stop reading from the socket
        2. Flush any buffered outgoing data
        3. Close the connection after send buffer is empty

        This is the recommended way to close connections from the server side,
        as it ensures response data is fully sent before closing.

        Example:
            def handler(conn, ev, data):
                if ev == MG_EV_HTTP_MSG:
                    conn.reply(200, b"Goodbye!")
                    conn.drain()  # Close after response is sent
        """
        ...

    def tls_init(self, opts: TlsOpts) -> None:
        """Initialize TLS/SSL on this connection.

        Args:
            opts: TlsOpts object with certificate, key, CA, etc.

        Example:
            # HTTPS server with custom certificate
            opts = TlsOpts(
                cert=open('server.crt', 'rb').read(),
                key=open('server.key', 'rb').read()
            )
            listener = manager.listen("https://0.0.0.0:443")
            listener.tls_init(opts)

            # HTTPS client with custom CA
            opts = TlsOpts(ca=open('custom-ca.crt', 'rb').read())
            conn = manager.connect("https://example.com")
            conn.tls_init(opts)
        """
        ...

    def tls_free(self) -> None:
        """Free TLS/SSL resources on this connection.

        Typically not needed as TLS is automatically freed when connection closes.
        """
        ...

    def __repr__(self) -> str: ...

class Manager:
    """Manage Mongoose event loop and provide Python callbacks."""

    def __init__(
        self,
        handler: Optional[EventHandler] = None,
        enable_wakeup: bool = False,
        error_handler: Optional[Callable[[Exception], Any]] = None,
    ) -> None:
        """Initialize event manager.

        Args:
            handler: Default event handler for all connections
            enable_wakeup: Enable wakeup support for multi-threaded scenarios
            error_handler: Optional callback invoked with the exception when
                an event handler raises. Defaults to traceback.print_exc().
        """
        ...

    def poll(self, timeout_ms: int = 0) -> None:
        """Drive the event loop once.

        Args:
            timeout_ms: Timeout in milliseconds (0 = non-blocking)

        Thread safety note: _freed flag is checked without lock. In multi-threaded scenarios,
        use close() only after all polling threads have stopped to avoid race conditions.

        Raises:
            RuntimeError: If manager has been freed
        """
        ...

    def listen(
        self, url: str, handler: Optional[EventHandler] = None, *, http: bool = False
    ) -> Connection:
        """Listen on a URL; handler is optional per-listener override.

        Args:
            url: URL to listen on (e.g., "http://0.0.0.0:8000", "tcp://0.0.0.0:1234")
            handler: Optional per-connection handler (overrides default)
            http: If True, use HTTP protocol handler

        Returns:
            Listener connection object

        Raises:
            RuntimeError: If failed to listen on URL
        """
        ...

    def connect(
        self, url: str, handler: Optional[EventHandler] = None, *, http: bool = False
    ) -> Connection:
        """Create an outbound connection and return immediately.

        Args:
            url: URL to connect to (e.g., "http://example.com", "tcp://example.com:1234")
            handler: Optional per-connection handler (overrides default)
            http: If True, use HTTP protocol handler

        Returns:
            Connection object

        Raises:
            RuntimeError: If failed to connect to URL
        """
        ...

    def mqtt_connect(
        self,
        url: str,
        handler: Optional[EventHandler] = None,
        client_id: str = "",
        username: str = "",
        password: str = "",
        clean_session: bool = True,
        keepalive: int = 60,
    ) -> Connection:
        """Connect to an MQTT broker.

        Args:
            url: Broker URL (e.g., 'mqtt://broker.hivemq.com:1883')
            handler: Event handler callback
            client_id: MQTT client ID (autogenerated if empty)
            username: MQTT username (optional)
            password: MQTT password (optional)
            clean_session: Clean session flag
            keepalive: Keep-alive interval in seconds

        Returns:
            Connection object

        Raises:
            RuntimeError: If failed to connect to broker
        """
        ...

    def mqtt_listen(self, url: str, handler: Optional[EventHandler] = None) -> Connection:
        """Listen for MQTT connections (broker mode).

        Args:
            url: Listen URL (e.g., 'mqtt://0.0.0.0:1883')
            handler: Event handler callback

        Returns:
            Listener connection object

        Raises:
            RuntimeError: If failed to listen for MQTT
        """
        ...

    def sntp_connect(self, url: str, handler: Optional[EventHandler] = None) -> Connection:
        """Connect to an SNTP (time) server.

        Triggers MG_EV_SNTP_TIME event when time is received.

        Args:
            url: SNTP server URL (e.g., 'udp://time.google.com:123')
            handler: Event handler callback

        Returns:
            Connection object

        Raises:
            RuntimeError: If failed to connect to SNTP server

        Example:
            def time_handler(conn, ev, data):
                if ev == MG_EV_SNTP_TIME:
                    # data is uint64_t epoch milliseconds
                    print(f"Time: {data} ms since epoch")

            conn = manager.sntp_connect("udp://time.google.com:123", time_handler)
            conn.sntp_request()  # Request time
        """
        ...

    def wakeup(self, connection_id: int, data: bytes = b"") -> bool:
        """Send a wakeup notification to a specific connection (thread-safe).

        Args:
            connection_id: The connection ID to wake up
            data: Optional data payload (delivered via MG_EV_WAKEUP event)

        Returns:
            True if wakeup was sent successfully

        Thread safety note: _freed flag is checked without lock. In multi-threaded scenarios,
        use close() only after all polling threads have stopped to avoid race conditions.

        Raises:
            RuntimeError: If manager has been freed
        """
        ...

    def timer_add(
        self,
        milliseconds: int,
        callback: Callable[[], None],
        *,
        repeat: bool = False,
        run_now: bool = False,
    ) -> "Timer":
        """Add a timer that calls a Python callback periodically.

        Args:
            milliseconds: Timer interval in milliseconds
            callback: Python callable (takes no arguments)
            repeat: If True, timer repeats; if False, runs once
            run_now: If True, callback is called immediately

        Returns:
            Timer object

        Note: Timers are automatically freed when they complete (MG_TIMER_AUTODELETE flag).
        The Timer object's __dealloc__ only releases the Python callback reference.

        Raises:
            RuntimeError: If manager has been freed or timer creation failed

        Example:
            def heartbeat():
                print("ping")

            timer = manager.timer_add(1000, heartbeat, repeat=True)
        """
        ...

    def close(self) -> None:
        """Free the underlying manager and release resources."""
        ...

class Timer:
    """Wrapper for Mongoose timer.

    Note: The underlying mg_timer is automatically freed by Mongoose when it completes
    (via MG_TIMER_AUTODELETE flag). This class only manages the Python callback reference.
    """

    ...

# JSON utilities
def json_get(data: Union[str, bytes], path: str) -> Optional[str]:
    """Extract a value from JSON by path (e.g., '$.user.name').

    Args:
        data: JSON string or bytes
        path: JSON path (e.g., '$.items[0].id')

    Returns:
        String value at path, or None if not found
    """
    ...

def json_get_num(
    data: Union[str, bytes], path: str, default: Optional[float] = None
) -> Optional[float]:
    """Extract a numeric value from JSON by path.

    Args:
        data: JSON string or bytes
        path: JSON path (e.g., '$.count')
        default: Default value if not found or not a number

    Returns:
        Float value at path, or default if not found
    """
    ...

def json_get_bool(
    data: Union[str, bytes], path: str, default: Optional[bool] = None
) -> Optional[bool]:
    """Extract a boolean value from JSON by path.

    Args:
        data: JSON string or bytes
        path: JSON path (e.g., '$.enabled')
        default: Default value if not found or not a boolean

    Returns:
        Boolean value at path, or default if not found
    """
    ...

def json_get_long(data: Union[str, bytes], path: str, default: int = 0) -> int:
    """Extract an integer value from JSON by path.

    Args:
        data: JSON string or bytes
        path: JSON path (e.g., '$.id')
        default: Default value if not found or not an integer

    Returns:
        Integer value at path, or default if not found
    """
    ...

def json_get_str(data: Union[str, bytes], path: str) -> Optional[str]:
    """Extract a string value from JSON by path (automatically unescapes).

    Args:
        data: JSON string or bytes
        path: JSON path (e.g., '$.message')

    Returns:
        Unescaped string value at path, or None if not found
    """
    ...

def url_encode(data: str) -> str:
    """URL-encode a string.

    Args:
        data: String to encode

    Returns:
        URL-encoded string
    """
    ...

def http_parse_multipart(
    body: Union[str, bytes], offset: int = 0
) -> Tuple[int, Optional[Dict[str, Union[str, bytes]]]]:
    """Parse the next multipart form part from HTTP body.

    Args:
        body: HTTP body (str or bytes)
        offset: Offset to start parsing from

    Returns:
        Tuple of (next_offset, part_dict) where part_dict contains:
        - 'name': form field name
        - 'filename': filename (if file upload)
        - 'body': part data as bytes
        Returns (0, None) if no more parts.
    """
    ...

def log_set(level: int) -> None:
    """Set the Mongoose C library log verbosity level.

    Args:
        level: One of MG_LL_NONE (0), MG_LL_ERROR (1), MG_LL_INFO (2),
               MG_LL_DEBUG (3), MG_LL_VERBOSE (4)
    """
    ...

def log_get() -> int:
    """Return the current Mongoose C library log verbosity level."""
    ...
