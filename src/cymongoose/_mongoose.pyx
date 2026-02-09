# cython: language_level=3, boundscheck=False, wraparound=False, cdivision=True
# distutils: language = c
"""
Cython bindings that expose a Python-friendly interface to the Mongoose
embedded networking library.
"""

# USE_NOGIL compile-time constant set via setup.py compile_time_env
# When 1: nogil is used for parallel execution (releases GIL for C calls)
# When 0: GIL is held for all C calls
# Configured in setup.py: USE_NOGIL = use_nogil
# NOTE: Mongoose's built-in TLS is event-loop based with no locks, so nogil is safe with TLS
IF USE_NOGIL:
    USE_NOGIL_ENABLED = True
ELSE:
    USE_NOGIL_ENABLED = False

from cpython.ref cimport PyObject, Py_INCREF, Py_DECREF
from cpython.bytes cimport PyBytes_FromStringAndSize
from cpython.unicode cimport PyUnicode_DecodeUTF8
from cpython.exc cimport PyErr_CheckSignals
from libc.stdint cimport uintptr_t, uint16_t, uint64_t
from libc.string cimport memset
from libc.stddef cimport size_t
from libc.stdlib cimport free, malloc
from libcpp cimport bool as cbool
from cython cimport sizeof

cdef extern from *:
    """
    #ifdef __APPLE__
    #include <machine/endian.h>
    #include <libkern/OSByteOrder.h>
    #define ntohs(x) OSSwapBigToHostInt16(x)
    #elif defined(_WIN32)
    #include <winsock2.h>
    #else
    #include <arpa/inet.h>
    #endif
    """
    uint16_t ntohs(uint16_t netshort) nogil

from .mongoose cimport (
    MG_EV_ERROR as C_MG_EV_ERROR,
    MG_EV_OPEN as C_MG_EV_OPEN,
    MG_EV_POLL as C_MG_EV_POLL,
    MG_EV_RESOLVE as C_MG_EV_RESOLVE,
    MG_EV_CONNECT as C_MG_EV_CONNECT,
    MG_EV_ACCEPT as C_MG_EV_ACCEPT,
    MG_EV_TLS_HS as C_MG_EV_TLS_HS,
    MG_EV_READ as C_MG_EV_READ,
    MG_EV_WRITE as C_MG_EV_WRITE,
    MG_EV_CLOSE as C_MG_EV_CLOSE,
    MG_EV_HTTP_HDRS as C_MG_EV_HTTP_HDRS,
    MG_EV_HTTP_MSG as C_MG_EV_HTTP_MSG,
    MG_EV_WS_OPEN as C_MG_EV_WS_OPEN,
    MG_EV_WS_MSG as C_MG_EV_WS_MSG,
    MG_EV_WS_CTL as C_MG_EV_WS_CTL,
    MG_EV_MQTT_CMD as C_MG_EV_MQTT_CMD,
    MG_EV_MQTT_MSG as C_MG_EV_MQTT_MSG,
    MG_EV_MQTT_OPEN as C_MG_EV_MQTT_OPEN,
    MG_EV_SNTP_TIME as C_MG_EV_SNTP_TIME,
    MG_EV_WAKEUP as C_MG_EV_WAKEUP,
    MG_EV_USER as C_MG_EV_USER,
    MG_MAX_HTTP_HEADERS,
    MG_LL_NONE as C_MG_LL_NONE,
    MG_LL_ERROR as C_MG_LL_ERROR,
    MG_LL_INFO as C_MG_LL_INFO,
    MG_LL_DEBUG as C_MG_LL_DEBUG,
    MG_LL_VERBOSE as C_MG_LL_VERBOSE,
    mg_log_level,
    mg_addr,
    mg_connection,
    mg_event_handler_t,
    mg_http_header,
    mg_http_listen,
    mg_http_message,
    mg_http_connect,
    mg_http_reply,
    mg_http_serve_dir,
    mg_http_serve_file,
    mg_http_serve_opts,
    mg_http_get_header,
    mg_http_get_var,
    mg_http_parse,
    mg_http_get_request_len,
    mg_http_printf_chunk,
    mg_http_write_chunk,
    mg_http_upload,
    mg_json_get,
    mg_json_get_tok,
    mg_json_get_num,
    mg_json_get_bool,
    mg_json_get_long,
    mg_json_get_str,
    mg_json_get_hex,
    mg_json_get_b64,
    mg_json_unescape,
    mg_json_next,
    mg_mgr,
    mg_mgr_init,
    mg_mgr_poll,
    mg_mgr_free,
    mg_listen,
    mg_connect,
    mg_send,
    mg_printf,
    mg_close_conn,
    mg_str,
    mg_str_n,
    mg_ws_message,
    mg_ws_send,
    mg_ws_printf,
    mg_ws_upgrade,
    mg_tls_opts,
    mg_tls_init,
    mg_tls_free,
    mg_wakeup,
    mg_wakeup_init,
    mg_url_encode,
    mg_http_next_multipart,
    mg_http_part,
    mg_http_status,
    mg_http_get_header_var,
    mg_http_bauth,
    mg_error,
    mg_resolve,
    mg_resolve_cancel,
    mg_mqtt_opts,
    mg_mqtt_message,
    mg_mqtt_connect,
    mg_mqtt_listen,
    mg_mqtt_login,
    mg_mqtt_pub,
    mg_mqtt_sub,
    mg_mqtt_ping,
    mg_mqtt_pong,
    mg_mqtt_disconnect,
    mg_sntp_connect,
    mg_sntp_request,
    mg_sntp_parse,
    mg_timer,
    mg_timer_fn_t,
    mg_timer_add,
    mg_timer_free,
    MG_TIMER_ONCE,
    MG_TIMER_REPEAT,
    MG_TIMER_RUN_NOW,
    MG_TIMER_AUTODELETE,
    WEBSOCKET_OP_TEXT as C_WEBSOCKET_OP_TEXT,
    WEBSOCKET_OP_BINARY as C_WEBSOCKET_OP_BINARY,
    WEBSOCKET_OP_PING as C_WEBSOCKET_OP_PING,
    WEBSOCKET_OP_PONG as C_WEBSOCKET_OP_PONG,
)

import traceback

__all__ = [
    "Manager",
    "Connection",
    "HttpMessage",
    "WsMessage",
    "MqttMessage",
    "TlsOpts",
    "Timer",
    "MG_EV_ERROR",
    "MG_EV_OPEN",
    "MG_EV_POLL",
    "MG_EV_RESOLVE",
    "MG_EV_CONNECT",
    "MG_EV_ACCEPT",
    "MG_EV_TLS_HS",
    "MG_EV_READ",
    "MG_EV_WRITE",
    "MG_EV_CLOSE",
    "MG_EV_HTTP_HDRS",
    "MG_EV_HTTP_MSG",
    "MG_EV_WS_OPEN",
    "MG_EV_WS_MSG",
    "MG_EV_WS_CTL",
    "MG_EV_MQTT_CMD",
    "MG_EV_MQTT_MSG",
    "MG_EV_MQTT_OPEN",
    "MG_EV_SNTP_TIME",
    "MG_EV_WAKEUP",
    "MG_EV_USER",
    "WEBSOCKET_OP_TEXT",
    "WEBSOCKET_OP_BINARY",
    "WEBSOCKET_OP_PING",
    "WEBSOCKET_OP_PONG",
    "json_get",
    "json_get_num",
    "json_get_bool",
    "json_get_long",
    "json_get_str",
    "url_encode",
    "http_parse_multipart",
    "log_set",
    "log_get",
    "MG_LL_NONE",
    "MG_LL_ERROR",
    "MG_LL_INFO",
    "MG_LL_DEBUG",
    "MG_LL_VERBOSE",
]

MG_EV_ERROR = C_MG_EV_ERROR
MG_EV_OPEN = C_MG_EV_OPEN
MG_EV_POLL = C_MG_EV_POLL
MG_EV_RESOLVE = C_MG_EV_RESOLVE
MG_EV_CONNECT = C_MG_EV_CONNECT
MG_EV_ACCEPT = C_MG_EV_ACCEPT
MG_EV_TLS_HS = C_MG_EV_TLS_HS
MG_EV_READ = C_MG_EV_READ
MG_EV_WRITE = C_MG_EV_WRITE
MG_EV_CLOSE = C_MG_EV_CLOSE
MG_EV_HTTP_HDRS = C_MG_EV_HTTP_HDRS
MG_EV_HTTP_MSG = C_MG_EV_HTTP_MSG
MG_EV_WS_OPEN = C_MG_EV_WS_OPEN
MG_EV_WS_MSG = C_MG_EV_WS_MSG
MG_EV_WS_CTL = C_MG_EV_WS_CTL
MG_EV_MQTT_CMD = C_MG_EV_MQTT_CMD
MG_EV_MQTT_MSG = C_MG_EV_MQTT_MSG
MG_EV_MQTT_OPEN = C_MG_EV_MQTT_OPEN
MG_EV_SNTP_TIME = C_MG_EV_SNTP_TIME
MG_EV_WAKEUP = C_MG_EV_WAKEUP
MG_EV_USER = C_MG_EV_USER

WEBSOCKET_OP_TEXT = C_WEBSOCKET_OP_TEXT
WEBSOCKET_OP_BINARY = C_WEBSOCKET_OP_BINARY
WEBSOCKET_OP_PING = C_WEBSOCKET_OP_PING
WEBSOCKET_OP_PONG = C_WEBSOCKET_OP_PONG

MG_LL_NONE = C_MG_LL_NONE
MG_LL_ERROR = C_MG_LL_ERROR
MG_LL_INFO = C_MG_LL_INFO
MG_LL_DEBUG = C_MG_LL_DEBUG
MG_LL_VERBOSE = C_MG_LL_VERBOSE


cdef inline bytes _mg_str_to_bytes(mg_str value):
    """Return a bytes copy of an mg_str."""
    if value.buf == NULL or value.len == 0:
        return b""
    return PyBytes_FromStringAndSize(value.buf, value.len)


cdef inline str _mg_str_to_text(mg_str value):
    """Return a Unicode string, decoding with UTF-8 and surrogate escape."""
    if value.buf == NULL or value.len == 0:
        return ""
    return PyUnicode_DecodeUTF8(value.buf, value.len, "surrogateescape")


cdef class HttpMessage:
    """Lightweight view over a struct mg_http_message."""

    cdef mg_http_message *_msg

    cdef void _assign(self, mg_http_message *msg):
        self._msg = msg

    def __bool__(self):
        return self._msg != NULL

    property method:
        def __get__(self):
            return _mg_str_to_text(self._msg.method) if self._msg != NULL else ""

    property uri:
        def __get__(self):
            return _mg_str_to_text(self._msg.uri) if self._msg != NULL else ""

    property query:
        def __get__(self):
            return _mg_str_to_text(self._msg.query) if self._msg != NULL else ""

    property proto:
        def __get__(self):
            return _mg_str_to_text(self._msg.proto) if self._msg != NULL else ""

    property body_bytes:
        def __get__(self):
            return _mg_str_to_bytes(self._msg.body) if self._msg != NULL else b""

    property body_text:
        def __get__(self):
            return _mg_str_to_text(self._msg.body) if self._msg != NULL else ""

    def header(self, name: str, default=None):
        """Return a HTTP header value or default when not present."""
        if self._msg == NULL:
            return default
        cdef bytes lookup = name.encode("utf-8")
        cdef mg_str *result = mg_http_get_header(self._msg, lookup)
        if result == NULL:
            return default
        return _mg_str_to_text(result[0])

    def headers(self):
        """Return all HTTP headers as a list of (name, value) tuples."""
        if self._msg == NULL:
            return []
        cdef mg_http_header header
        cdef size_t idx
        result = []
        for idx in range(MG_MAX_HTTP_HEADERS):
            header = self._msg.headers[idx]
            if header.name.len == 0:
                break
            result.append((_mg_str_to_text(header.name), _mg_str_to_text(header.value)))
        return result

    def query_var(self, name: str):
        """Extract a query string parameter.

        Raises ValueError if the decoded value exceeds 2048 bytes.
        """
        if self._msg == NULL:
            return None
        cdef bytes name_b = name.encode("utf-8")
        cdef char buffer[2048]
        cdef int rc = mg_http_get_var(&self._msg.query, name_b, buffer, sizeof(buffer))
        if rc == -3:
            raise ValueError(
                f"Query parameter '{name}' value exceeds 2048-byte buffer limit"
            )
        if rc <= 0:
            return None
        return buffer[:rc].decode("utf-8", "surrogateescape")

    def status(self):
        """Return HTTP status code from response message.

        Returns:
            int: Status code (e.g., 200, 404) or None if not available
        """
        if self._msg == NULL:
            return None
        return mg_http_status(self._msg)

    def header_var(self, header_name: str, var_name: str):
        """Parse a variable from a header value.

        Useful for parsing sub-values like charset from Content-Type header.
        Example: header_var("Content-Type", "charset") -> "utf-8"

        Args:
            header_name: Name of the header (e.g., "Content-Type")
            var_name: Name of the variable to extract (e.g., "charset")

        Returns:
            str: The variable value or None if not found
        """
        if self._msg == NULL:
            return None

        # Get the header value first
        cdef bytes header_name_b = header_name.encode("utf-8")
        cdef mg_str *header_value = mg_http_get_header(self._msg, header_name_b)
        if header_value == NULL:
            return None

        # Parse variable from header value
        cdef bytes var_name_b = var_name.encode("utf-8")
        cdef mg_str var_value_str = mg_http_get_header_var(header_value[0], mg_str_n(var_name_b, len(var_name_b)))

        if var_value_str.buf == NULL or var_value_str.len == 0:
            return None

        return _mg_str_to_text(var_value_str)


cdef class WsMessage:
    """View over an incoming WebSocket frame."""

    cdef mg_ws_message *_msg

    cdef void _assign(self, mg_ws_message *msg):
        self._msg = msg

    property data:
        def __get__(self):
            return _mg_str_to_bytes(self._msg.data) if self._msg != NULL else b""

    property text:
        def __get__(self):
            return _mg_str_to_text(self._msg.data) if self._msg != NULL else ""

    property flags:
        def __get__(self):
            return self._msg.flags if self._msg != NULL else 0


cdef class MqttMessage:
    """View over an incoming MQTT message."""

    cdef mg_mqtt_message *_msg

    cdef void _assign(self, mg_mqtt_message *msg):
        self._msg = msg

    property topic:
        def __get__(self):
            return _mg_str_to_text(self._msg.topic) if self._msg != NULL else ""

    property data:
        def __get__(self):
            return _mg_str_to_bytes(self._msg.data) if self._msg != NULL else b""

    property text:
        def __get__(self):
            return _mg_str_to_text(self._msg.data) if self._msg != NULL else ""

    property id:
        def __get__(self):
            return self._msg.id if self._msg != NULL else 0

    property cmd:
        def __get__(self):
            return self._msg.cmd if self._msg != NULL else 0

    property qos:
        def __get__(self):
            return self._msg.qos if self._msg != NULL else 0

    property ack:
        def __get__(self):
            return self._msg.ack if self._msg != NULL else 0


cdef class TlsOpts:
    """TLS configuration options for secure connections.

    Used to configure TLS/SSL settings for HTTPS, WSS, MQTTS, etc.
    """
    cdef public bytes ca
    cdef public bytes cert
    cdef public bytes key
    cdef public bytes name
    cdef public bint skip_verification

    def __init__(self, ca=None, cert=None, key=None, name=None, skip_verification=False):
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
        self.ca = ca.encode('utf-8') if isinstance(ca, str) else (ca if ca else b'')
        self.cert = cert.encode('utf-8') if isinstance(cert, str) else (cert if cert else b'')
        self.key = key.encode('utf-8') if isinstance(key, str) else (key if key else b'')
        self.name = name.encode('utf-8') if isinstance(name, str) else (name if name else b'')
        self.skip_verification = skip_verification


cdef class Connection:
    """Wrapper around mg_connection pointers."""

    cdef mg_connection *_conn
    cdef Manager _manager
    cdef object _handler
    cdef object _userdata

    def __cinit__(self):
        self._conn = NULL
        self._manager = None
        self._handler = None
        self._userdata = None

    cdef void _bind(self, Manager manager, mg_connection *conn, object handler):
        self._manager = manager
        self._conn = conn
        self._handler = handler

    cdef mg_connection *_ptr(self):
        if self._conn == NULL:
            raise RuntimeError("Connection has been closed")
        return self._conn

    @property
    def handler(self):
        return self._handler

    def set_handler(self, handler):
        """Assign a per-connection event handler."""
        self._handler = handler

    @property
    def userdata(self):
        return self._userdata

    @userdata.setter
    def userdata(self, value):
        self._userdata = value

    @property
    def id(self):
        """Return connection ID."""
        return self._conn.id if self._conn != NULL else 0

    @property
    def is_listening(self):
        return self._conn.is_listening != 0 if self._conn != NULL else False

    @property
    def is_closing(self):
        return self._conn.is_closing != 0 if self._conn != NULL else True

    @property
    def local_addr(self):
        """Return local address as (ip, port, is_ipv6) tuple."""
        if self._conn == NULL:
            return None
        cdef mg_addr addr
        cdef uint16_t net_port
        cdef uint16_t host_port
        cdef bint is_ipv6

        # Copy addr struct and convert port
        addr = self._conn.loc
        net_port = addr.port
        host_port = ntohs(net_port)
        is_ipv6 = addr.is_ip6

        if is_ipv6:
            # IPv6 address formatting
            parts = []
            for i in range(8):
                parts.append(f"{addr.ip[i*2]:02x}{addr.ip[i*2+1]:02x}")
            ip_str = ":".join(parts)
        else:
            # IPv4 address
            ip_str = f"{addr.ip[0]}.{addr.ip[1]}.{addr.ip[2]}.{addr.ip[3]}"
        return (ip_str, host_port, bool(is_ipv6))

    @property
    def remote_addr(self):
        """Return remote address as (ip, port, is_ipv6) tuple."""
        if self._conn == NULL:
            return None
        cdef mg_addr addr
        cdef uint16_t net_port
        cdef uint16_t host_port
        cdef bint is_ipv6

        # Copy addr struct and convert port
        addr = self._conn.rem
        net_port = addr.port
        host_port = ntohs(net_port)
        is_ipv6 = addr.is_ip6

        if is_ipv6:
            # IPv6 address formatting
            parts = []
            for i in range(8):
                parts.append(f"{addr.ip[i*2]:02x}{addr.ip[i*2+1]:02x}")
            ip_str = ":".join(parts)
        else:
            # IPv4 address
            ip_str = f"{addr.ip[0]}.{addr.ip[1]}.{addr.ip[2]}.{addr.ip[3]}"
        return (ip_str, host_port, bool(is_ipv6))

    def send(self, data):
        """Send raw bytes to the peer."""
        cdef bytes payload
        if isinstance(data, str):
            payload = (<str>data).encode("utf-8")
        else:
            payload = bytes(data)
        cdef const char *buf = payload
        cdef size_t length = len(payload)
        cdef mg_connection *conn = self._ptr()
        cdef bint result
        IF USE_NOGIL:
            with nogil:
                result = mg_send(conn, buf, length)
        ELSE:
            result = mg_send(conn, buf, length)
        if not result:
            raise RuntimeError("mg_send failed")

    def reply(self, int status_code, body=b"", headers=None):
        """Send a HTTP reply (final response)."""
        if isinstance(body, str):
            body_bytes = body.encode("utf-8")
        else:
            body_bytes = bytes(body)
        if headers is None:
            header_lines = ["Content-Type: text/plain\r\n"]
        else:
            header_lines = [f"{k}: {v}\r\n" for k, v in headers.items()]
        headers_bytes = "".join(header_lines).encode("utf-8")
        # Keep Python bytes objects alive during nogil C call - pointers reference their buffers
        cdef bytes headers_b = headers_bytes
        cdef bytes body_b = body_bytes
        cdef const char *headers_c = headers_b if headers_b else b""
        cdef const char *body_fmt_c = b"%s"
        cdef const char *body_c = body_b
        cdef mg_connection *conn = self._ptr()
        IF USE_NOGIL:
            with nogil:
                mg_http_reply(conn, status_code, headers_c, body_fmt_c, body_c)
        ELSE:
            mg_http_reply(conn, status_code, headers_c, body_fmt_c, body_c)

    def serve_dir(self, HttpMessage message, root_dir: str, extra_headers: str = "", mime_types: str = "", page404: str = ""):
        """Serve files from a directory using Mongoose's built-in static handler."""
        if message._msg == NULL:
            raise ValueError("HttpMessage is not valid for this event")
        cdef mg_http_serve_opts opts
        memset(&opts, 0, sizeof(mg_http_serve_opts))
        # Keep Python bytes objects alive - opts struct contains pointers to their buffers
        cdef bytes root_b = root_dir.encode("utf-8")
        opts.root_dir = root_b
        cdef bytes extra_headers_b
        cdef bytes mime_types_b
        cdef bytes page404_b
        if extra_headers:
            extra_headers_b = extra_headers.encode("utf-8")
            opts.extra_headers = extra_headers_b
        if mime_types:
            mime_types_b = mime_types.encode("utf-8")
            opts.mime_types = mime_types_b
        if page404:
            page404_b = page404.encode("utf-8")
            opts.page404 = page404_b
        cdef mg_connection *conn = self._ptr()
        cdef mg_http_message *msg = message._msg
        IF USE_NOGIL:
            with nogil:
                mg_http_serve_dir(conn, msg, &opts)
        ELSE:
            mg_http_serve_dir(conn, msg, &opts)

    def serve_file(self, HttpMessage message, path: str, extra_headers: str = "", mime_types: str = ""):
        """Serve a single file using Mongoose's built-in static handler."""
        if message._msg == NULL:
            raise ValueError("HttpMessage is not valid for this event")
        cdef mg_http_serve_opts opts
        memset(&opts, 0, sizeof(mg_http_serve_opts))
        # Keep Python bytes objects alive - path_b and opts struct pointers reference their buffers
        cdef bytes path_b = path.encode("utf-8")
        cdef bytes extra_headers_b
        cdef bytes mime_types_b
        if extra_headers:
            extra_headers_b = extra_headers.encode("utf-8")
            opts.extra_headers = extra_headers_b
        if mime_types:
            mime_types_b = mime_types.encode("utf-8")
            opts.mime_types = mime_types_b
        cdef mg_connection *conn = self._ptr()
        cdef mg_http_message *msg = message._msg
        cdef const char *path_c = path_b
        IF USE_NOGIL:
            with nogil:
                mg_http_serve_file(conn, msg, path_c, &opts)
        ELSE:
            mg_http_serve_file(conn, msg, path_c, &opts)

    def ws_upgrade(self, HttpMessage message, extra_headers=None):
        """Upgrade HTTP connection to WebSocket.

        Args:
            message: The HttpMessage from MG_EV_HTTP_MSG event
            extra_headers: Optional dict of extra headers to send in upgrade response
        """
        if message._msg == NULL:
            raise ValueError("HttpMessage is not valid for this event")

        cdef const char *fmt = NULL
        cdef bytes headers_b
        if extra_headers:
            headers_str = "\r\n".join(f"{k}: {v}" for k, v in extra_headers.items())
            # Keep Python bytes object alive - fmt pointer references its buffer
            headers_b = headers_str.encode("utf-8")
            fmt = headers_b

        cdef mg_connection *conn = self._ptr()
        cdef mg_http_message *msg = message._msg
        IF USE_NOGIL:
            with nogil:
                mg_ws_upgrade(conn, msg, fmt)
        ELSE:
            mg_ws_upgrade(conn, msg, fmt)

    def ws_send(self, data, op=WEBSOCKET_OP_TEXT):
        """Send a WebSocket frame."""
        if isinstance(data, str):
            payload = data.encode("utf-8")
        else:
            payload = bytes(data)
        cdef bytes payload_b = payload
        cdef const char *buf = payload_b
        cdef size_t length = len(payload_b)
        cdef mg_connection *conn = self._ptr()
        cdef int op_c = op
        IF USE_NOGIL:
            with nogil:
                mg_ws_send(conn, buf, length, op_c)
        ELSE:
            mg_ws_send(conn, buf, length, op_c)

    def mqtt_pub(self, topic: str, message, qos=0, retain=False):
        """Publish an MQTT message.

        Args:
            topic: MQTT topic
            message: Message payload (str or bytes)
            qos: Quality of service (0, 1, or 2)
            retain: Retain flag

        Returns:
            Message ID
        """
        cdef mg_mqtt_opts opts
        memset(&opts, 0, sizeof(mg_mqtt_opts))

        cdef bytes topic_b = topic.encode("utf-8")
        cdef bytes msg_b
        if isinstance(message, str):
            msg_b = message.encode("utf-8")
        else:
            msg_b = bytes(message)

        opts.topic = mg_str_n(topic_b, len(topic_b))
        opts.message = mg_str_n(msg_b, len(msg_b))
        opts.qos = qos
        opts.retain = retain

        cdef mg_connection *conn = self._ptr()
        cdef uint16_t msg_id
        IF USE_NOGIL:
            with nogil:
                msg_id = mg_mqtt_pub(conn, &opts)
        ELSE:
            msg_id = mg_mqtt_pub(conn, &opts)
        return msg_id

    def mqtt_sub(self, topic: str, qos=0):
        """Subscribe to an MQTT topic.

        Args:
            topic: MQTT topic (can include wildcards)
            qos: Quality of service (0, 1, or 2)
        """
        cdef mg_mqtt_opts opts
        memset(&opts, 0, sizeof(mg_mqtt_opts))

        cdef bytes topic_b = topic.encode("utf-8")
        opts.topic = mg_str_n(topic_b, len(topic_b))
        opts.qos = qos

        cdef mg_connection *conn = self._ptr()
        IF USE_NOGIL:
            with nogil:
                mg_mqtt_sub(conn, &opts)
        ELSE:
            mg_mqtt_sub(conn, &opts)

    def mqtt_ping(self):
        """Send MQTT ping."""
        cdef mg_connection *conn = self._ptr()
        IF USE_NOGIL:
            with nogil:
                mg_mqtt_ping(conn)
        ELSE:
            mg_mqtt_ping(conn)

    def mqtt_pong(self):
        """Send MQTT pong."""
        cdef mg_connection *conn = self._ptr()
        IF USE_NOGIL:
            with nogil:
                mg_mqtt_pong(conn)
        ELSE:
            mg_mqtt_pong(conn)

    def mqtt_disconnect(self):
        """Send MQTT disconnect message.

        Gracefully disconnects from MQTT broker by sending a DISCONNECT packet.
        """
        cdef mg_mqtt_opts opts
        memset(&opts, 0, sizeof(opts))
        cdef mg_connection *conn = self._ptr()
        IF USE_NOGIL:
            with nogil:
                mg_mqtt_disconnect(conn, &opts)
        ELSE:
            mg_mqtt_disconnect(conn, &opts)

    def error(self, message: str):
        """Trigger an error event on this connection.

        Args:
            message: Error message
        """
        cdef bytes msg_b = message.encode("utf-8")
        cdef mg_connection *conn = self._ptr()
        cdef const char *msg_ptr = msg_b
        mg_error(conn, b"%s", <char*>msg_ptr)

    @property
    def is_client(self):
        """Return True if this is a client connection."""
        return self._conn.is_client != 0 if self._conn != NULL else False

    @property
    def is_tls(self):
        """Return True if this connection uses TLS."""
        return self._conn.is_tls != 0 if self._conn != NULL else False

    @property
    def is_udp(self):
        """Return True if this is a UDP connection."""
        return self._conn.is_udp != 0 if self._conn != NULL else False

    @property
    def is_websocket(self):
        """Return True if this is a WebSocket connection."""
        return self._conn.is_websocket != 0 if self._conn != NULL else False

    @property
    def is_readable(self):
        """Return True if connection has data to read."""
        return self._conn.is_readable != 0 if self._conn != NULL else False

    @property
    def is_writable(self):
        """Return True if connection can be written to."""
        return self._conn.is_writable != 0 if self._conn != NULL else False

    @property
    def is_full(self):
        """Return True if receive buffer is full (backpressure - stop reads)."""
        return self._conn.is_full != 0 if self._conn != NULL else False

    @property
    def is_draining(self):
        """Return True if connection is draining (sending remaining data before close)."""
        return self._conn.is_draining != 0 if self._conn != NULL else False

    @property
    def recv_len(self):
        """Return number of bytes in receive buffer."""
        return self._conn.recv.len if self._conn != NULL else 0

    @property
    def send_len(self):
        """Return number of bytes in send buffer."""
        return self._conn.send.len if self._conn != NULL else 0

    @property
    def recv_size(self):
        """Return total allocated size of receive buffer."""
        return self._conn.recv.size if self._conn != NULL else 0

    @property
    def send_size(self):
        """Return total allocated size of send buffer."""
        return self._conn.send.size if self._conn != NULL else 0

    def recv_data(self, length: int = -1):
        """Read data from receive buffer without consuming it.

        Args:
            length: Number of bytes to read, or -1 for all

        Returns:
            bytes: Data from receive buffer
        """
        if self._conn == NULL:
            return b""
        cdef size_t read_len = self._conn.recv.len
        if length >= 0 and <size_t>length < read_len:
            read_len = <size_t>length
        if read_len == 0:
            return b""
        return (<char*>self._conn.recv.buf)[:read_len]

    def send_data(self, length: int = -1):
        """Read data from send buffer without consuming it.

        Args:
            length: Number of bytes to read, or -1 for all

        Returns:
            bytes: Data from send buffer
        """
        if self._conn == NULL:
            return b""
        cdef size_t read_len = self._conn.send.len
        if length >= 0 and <size_t>length < read_len:
            read_len = <size_t>length
        if read_len == 0:
            return b""
        return (<char*>self._conn.send.buf)[:read_len]

    def resolve(self, url: str):
        """Resolve a hostname asynchronously.

        Triggers MG_EV_RESOLVE event when DNS lookup completes.

        Args:
            url: URL to resolve (e.g., "google.com" or "tcp://example.com:80")
        """
        cdef bytes url_b = url.encode("utf-8")
        cdef const char *url_c = url_b
        cdef mg_connection *conn = self._ptr()
        IF USE_NOGIL:
            with nogil:
                mg_resolve(conn, url_c)
        ELSE:
            mg_resolve(conn, url_c)

    def resolve_cancel(self):
        """Cancel an ongoing DNS resolution."""
        cdef mg_connection *conn = self._ptr()
        IF USE_NOGIL:
            with nogil:
                mg_resolve_cancel(conn)
        ELSE:
            mg_resolve_cancel(conn)

    def http_basic_auth(self, username: str, password: str):
        """Send HTTP Basic Authentication credentials.

        Typically used on client connections to authenticate with a server.

        Args:
            username: Username for basic auth
            password: Password for basic auth
        """
        cdef bytes user_b = username.encode("utf-8")
        cdef bytes pass_b = password.encode("utf-8")
        cdef const char *user_c = user_b
        cdef const char *pass_c = pass_b
        cdef mg_connection *conn = self._ptr()
        mg_http_bauth(conn, user_c, pass_c)

    def sntp_request(self):
        """Send an SNTP time request.

        Use on a connection created with Manager.sntp_connect().
        Triggers MG_EV_SNTP_TIME event when response is received.
        """
        cdef mg_connection *conn = self._ptr()
        IF USE_NOGIL:
            with nogil:
                mg_sntp_request(conn)
        ELSE:
            mg_sntp_request(conn)

    def http_chunk(self, data):
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
        cdef bytes chunk_data
        if isinstance(data, str):
            chunk_data = data.encode("utf-8")
        else:
            chunk_data = bytes(data)

        cdef mg_connection *conn = self._ptr()
        cdef const char *buf_ptr
        cdef size_t buf_len

        if len(chunk_data) == 0:
            # Empty chunk signals end
            IF USE_NOGIL:
                with nogil:
                    mg_http_write_chunk(conn, NULL, 0)
            ELSE:
                mg_http_write_chunk(conn, NULL, 0)
        else:
            buf_ptr = chunk_data
            buf_len = len(chunk_data)
            IF USE_NOGIL:
                with nogil:
                    mg_http_write_chunk(conn, buf_ptr, buf_len)
            ELSE:
                mg_http_write_chunk(conn, buf_ptr, buf_len)

    def http_sse(self, event_type: str, data: str):
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
        cdef bytes event_b = event_type.encode("utf-8")
        cdef bytes data_b = data.encode("utf-8")
        # SSE format: "event: <type>\ndata: <data>\n\n"
        cdef bytes sse_msg = b"event: " + event_b + b"\ndata: " + data_b + b"\n\n"
        cdef mg_connection *conn = self._ptr()
        cdef const char *msg_ptr = sse_msg
        cdef size_t msg_len = len(sse_msg)
        IF USE_NOGIL:
            with nogil:
                mg_http_write_chunk(conn, msg_ptr, msg_len)
        ELSE:
            mg_http_write_chunk(conn, msg_ptr, msg_len)

    def close(self):
        """Immediately close the connection.

        For graceful shutdown, use drain() instead to let buffered data flush first.
        """
        cdef mg_connection *conn = self._conn
        if conn != NULL:
            IF USE_NOGIL:
                with nogil:
                    mg_close_conn(conn)
            ELSE:
                mg_close_conn(conn)

    def drain(self):
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
        cdef mg_connection *conn = self._conn
        if conn != NULL:
            conn.is_draining = 1

    def tls_init(self, TlsOpts opts):
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
        cdef mg_tls_opts c_opts
        memset(&c_opts, 0, sizeof(c_opts))

        # Set certificate fields
        if len(opts.ca) > 0:
            c_opts.ca = mg_str_n(opts.ca, len(opts.ca))
        if len(opts.cert) > 0:
            c_opts.cert = mg_str_n(opts.cert, len(opts.cert))
        if len(opts.key) > 0:
            c_opts.key = mg_str_n(opts.key, len(opts.key))
        if len(opts.name) > 0:
            c_opts.name = mg_str_n(opts.name, len(opts.name))

        c_opts.skip_verification = 1 if opts.skip_verification else 0

        cdef mg_connection *conn = self._ptr()
        IF USE_NOGIL:
            with nogil:
                mg_tls_init(conn, &c_opts)
        ELSE:
            mg_tls_init(conn, &c_opts)

    def tls_free(self):
        """Free TLS/SSL resources on this connection.

        Typically not needed as TLS is automatically freed when connection closes.
        """
        cdef mg_connection *conn = self._ptr()
        IF USE_NOGIL:
            with nogil:
                mg_tls_free(conn)
        ELSE:
            mg_tls_free(conn)

    def __repr__(self):
        if self._conn == NULL:
            return "<Connection closed>"
        return f"<Connection id={self._conn.id} readable={bool(self._conn.is_readable)} writable={bool(self._conn.is_writable)}>"


cdef class Manager:
    """Manage Mongoose event loop and provide Python callbacks."""

    cdef mg_mgr _mgr
    cdef object _default_handler
    cdef object _error_handler
    cdef dict _connections
    cdef PyObject *_self_ref
    cdef bint _freed

    def __cinit__(self, handler=None, enable_wakeup=False, error_handler=None):
        self._default_handler = handler
        self._error_handler = error_handler
        self._connections = {}
        self._self_ref = <PyObject*> self
        Py_INCREF(<object>self._self_ref)
        mg_mgr_init(&self._mgr)
        self._mgr.userdata = <void*> self
        self._freed = False
        if enable_wakeup:
            if not mg_wakeup_init(&self._mgr):
                raise RuntimeError("Failed to initialize wakeup support")

    def __dealloc__(self):
        if not self._freed:
            mg_mgr_free(&self._mgr)
            self._freed = True
        self._mgr.userdata = NULL
        if self._self_ref != NULL:
            Py_DECREF(<object>self._self_ref)
            self._self_ref = NULL

    cdef Connection _ensure_connection(self, mg_connection *conn):
        cdef uintptr_t key = <uintptr_t> conn
        cdef Connection py_conn
        py_conn = self._connections.get(key, None)
        if py_conn is None:
            py_conn = Connection.__new__(Connection)
            py_conn._bind(self, conn, None)
            self._connections[key] = py_conn
        elif py_conn._conn == NULL:
            py_conn._conn = conn
        return py_conn

    cdef void _drop_connection(self, mg_connection *conn):
        cdef uintptr_t key = <uintptr_t> conn
        cdef Connection py_conn
        py_conn = self._connections.pop(key, None)
        if py_conn is not None:
            py_conn._conn = <mg_connection*>NULL

    cdef object _resolve_handler(self, Connection conn):
        if conn._handler is not None:
            return conn._handler
        return self._default_handler

    cdef object _wrap_event_data(self, int ev, void *ev_data):
        cdef HttpMessage view
        cdef WsMessage ws
        cdef MqttMessage mqtt
        cdef mg_str *wakeup_data
        if ev == MG_EV_HTTP_MSG or ev == MG_EV_HTTP_HDRS or ev == MG_EV_WS_OPEN:
            if ev_data != NULL:
                view = HttpMessage.__new__(HttpMessage)
                view._assign(<mg_http_message*> ev_data)
                return view
            return None
        elif ev == MG_EV_WS_MSG:
            if ev_data != NULL:
                ws = WsMessage.__new__(WsMessage)
                ws._assign(<mg_ws_message*> ev_data)
                return ws
            return None
        elif ev == MG_EV_MQTT_MSG or ev == MG_EV_MQTT_CMD:
            if ev_data != NULL:
                mqtt = MqttMessage.__new__(MqttMessage)
                mqtt._assign(<mg_mqtt_message*> ev_data)
                return mqtt
            return None
        elif ev == MG_EV_MQTT_OPEN and ev_data != NULL:
            # MQTT_OPEN provides a pointer to connection status code
            return (<int*> ev_data)[0]
        elif ev == MG_EV_ERROR and ev_data != NULL:
            return (<char*> ev_data).decode("utf-8", "ignore")
        elif ev == MG_EV_WAKEUP and ev_data != NULL:
            wakeup_data = <mg_str*> ev_data
            return _mg_str_to_bytes(wakeup_data[0])
        elif ev == C_MG_EV_SNTP_TIME and ev_data != NULL:
            # SNTP provides uint64_t* epoch milliseconds
            return (<uint64_t*> ev_data)[0]
        return None

    def poll(self, int timeout_ms=0):
        """Drive the event loop once.

        Thread safety note: _freed flag is checked without lock. In multi-threaded scenarios,
        use close() only after all polling threads have stopped to avoid race conditions.
        """
        if self._freed:
            raise RuntimeError("Manager has been freed")
        with nogil:
            mg_mgr_poll(&self._mgr, timeout_ms)
        # Check for pending signals (e.g., KeyboardInterrupt from Ctrl+C)
        # This ensures signals received during nogil section are processed
        # PyErr_CheckSignals() returns -1 if a signal is pending and raises the exception
        if PyErr_CheckSignals() < 0:
            # Exception was set by PyErr_CheckSignals, Cython will propagate it
            pass

    def listen(self, url: str, handler=None, *, http=False):
        """Listen on a URL; handler is optional per-listener override."""
        cdef bytes url_b = url.encode("utf-8")
        cdef mg_connection *conn
        if http:
            conn = mg_http_listen(&self._mgr, url_b, _event_bridge, NULL)
        else:
            conn = mg_listen(&self._mgr, url_b, _event_bridge, NULL)
        if conn == NULL:
            raise RuntimeError(f"Failed to listen on '{url}'")
        py_conn = self._ensure_connection(conn)
        py_conn._handler = handler
        return py_conn

    def connect(self, url: str, handler=None, *, http=False):
        """Create an outbound connection and return immediately."""
        cdef bytes url_b = url.encode("utf-8")
        cdef mg_connection *conn
        if http:
            conn = mg_http_connect(&self._mgr, url_b, _event_bridge, NULL)
        else:
            conn = mg_connect(&self._mgr, url_b, _event_bridge, NULL)
        if conn == NULL:
            raise RuntimeError(f"Failed to connect to '{url}'")
        py_conn = self._ensure_connection(conn)
        py_conn._handler = handler
        return py_conn

    def mqtt_connect(self, url: str, handler=None, client_id="", username="", password="", clean_session=True, keepalive=60):
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
        """
        cdef mg_mqtt_opts opts
        memset(&opts, 0, sizeof(mg_mqtt_opts))

        cdef bytes client_id_b = client_id.encode("utf-8") if client_id else b""
        cdef bytes user_b = username.encode("utf-8") if username else b""
        cdef bytes pass_b = password.encode("utf-8") if password else b""

        if client_id_b:
            opts.client_id = mg_str_n(client_id_b, len(client_id_b))
        if user_b:
            opts.user = mg_str_n(user_b, len(user_b))
        if pass_b:
            opts.password = mg_str_n(pass_b, len(pass_b))

        opts.clean = clean_session
        opts.keepalive = keepalive
        opts.version = 4  # MQTT 3.1.1

        cdef bytes url_b = url.encode("utf-8")
        cdef mg_connection *conn = mg_mqtt_connect(&self._mgr, url_b, &opts, _event_bridge, NULL)
        if conn == NULL:
            raise RuntimeError(f"Failed to connect to MQTT broker '{url}'")

        py_conn = self._ensure_connection(conn)
        py_conn._handler = handler
        return py_conn

    def mqtt_listen(self, url: str, handler=None):
        """Listen for MQTT connections (broker mode).

        Args:
            url: Listen URL (e.g., 'mqtt://0.0.0.0:1883')
            handler: Event handler callback

        Returns:
            Listener connection object
        """
        cdef bytes url_b = url.encode("utf-8")
        cdef mg_connection *conn = mg_mqtt_listen(&self._mgr, url_b, _event_bridge, NULL)
        if conn == NULL:
            raise RuntimeError(f"Failed to listen for MQTT on '{url}'")

        py_conn = self._ensure_connection(conn)
        py_conn._handler = handler
        return py_conn

    def sntp_connect(self, url: str, handler=None):
        """Connect to an SNTP (time) server.

        Triggers MG_EV_SNTP_TIME event when time is received.

        Args:
            url: SNTP server URL (e.g., 'udp://time.google.com:123')
            handler: Event handler callback

        Returns:
            Connection object

        Example:
            def time_handler(conn, ev, data):
                if ev == MG_EV_SNTP_TIME:
                    # data is uint64_t epoch milliseconds
                    print(f"Time: {data} ms since epoch")

            conn = manager.sntp_connect("udp://time.google.com:123", time_handler)
            conn.sntp_request()  # Request time
        """
        cdef bytes url_b = url.encode("utf-8")
        cdef mg_connection *conn = mg_sntp_connect(&self._mgr, url_b, _event_bridge, NULL)
        if conn == NULL:
            raise RuntimeError(f"Failed to connect to SNTP server '{url}'")

        py_conn = self._ensure_connection(conn)
        py_conn._handler = handler
        return py_conn

    def wakeup(self, connection_id: int, data: bytes = b""):
        """Send a wakeup notification to a specific connection (thread-safe).

        Args:
            connection_id: The connection ID to wake up
            data: Optional data payload (delivered via MG_EV_WAKEUP event)

        Returns:
            True if wakeup was sent successfully

        Thread safety note: _freed flag is checked without lock. In multi-threaded scenarios,
        use close() only after all polling threads have stopped to avoid race conditions.
        """
        if self._freed:
            raise RuntimeError("Manager has been freed")
        cdef bytes data_b = data
        cdef const void *buf = <const void*><char*>data_b if len(data_b) > 0 else NULL
        cdef size_t len_data = len(data_b)
        cdef unsigned long conn_id = <unsigned long>connection_id
        cdef bint result
        IF USE_NOGIL:
            with nogil:
                result = mg_wakeup(&self._mgr, conn_id, buf, len_data)
        ELSE:
            result = mg_wakeup(&self._mgr, conn_id, buf, len_data)
        return result

    def timer_add(self, milliseconds: int, callback, *, repeat=False, run_now=False):
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

        Example:
            def heartbeat():
                print("ping")

            timer = manager.timer_add(1000, heartbeat, repeat=True)
        """
        if self._freed:
            raise RuntimeError("Manager has been freed")

        cdef unsigned flags = MG_TIMER_AUTODELETE
        if repeat:
            flags |= MG_TIMER_REPEAT
        if run_now:
            flags |= MG_TIMER_RUN_NOW

        # Create Timer wrapper
        cdef Timer timer = Timer.__new__(Timer)

        # Add timer with callback bridge
        cdef mg_timer *timer_ptr = mg_timer_add(
            &self._mgr,
            <uint64_t>milliseconds,
            flags,
            _timer_callback,
            <void*><PyObject*>callback
        )

        if timer_ptr == NULL:
            raise RuntimeError("Failed to add timer")

        # Setup Timer object - call cdef method directly
        timer._timer = timer_ptr
        timer._callback = callback
        timer._callback_ref = <PyObject*>callback
        Py_INCREF(callback)

        return timer

    def run(self, int poll_ms=100):
        """Run the event loop, blocking until SIGINT or SIGTERM.

        Installs signal handlers for graceful shutdown, runs the poll loop,
        and calls close() when done. Original signal handlers are restored.

        Args:
            poll_ms: Poll timeout in milliseconds (default: 100)
        """
        import signal as _signal

        stop = False

        def _stop_handler(sig, frame):
            nonlocal stop
            stop = True

        old_int = _signal.signal(_signal.SIGINT, _stop_handler)
        old_term = _signal.signal(_signal.SIGTERM, _stop_handler)
        try:
            while not stop:
                self.poll(poll_ms)
        finally:
            _signal.signal(_signal.SIGINT, old_int)
            _signal.signal(_signal.SIGTERM, old_term)
            self.close()

    def close(self):
        """Free the underlying manager and release resources."""
        if not self._freed:
            mg_mgr_free(&self._mgr)
            self._freed = True
            self._connections.clear()
            self._mgr.userdata = NULL


cdef void _event_bridge(mg_connection *conn, int ev, void *ev_data) noexcept with gil:
    """Global callback that routes events back into Python."""
    cdef Manager manager
    cdef PyObject *manager_obj = NULL
    cdef Connection py_conn
    if conn.mgr == NULL:
        return
    manager_obj = <PyObject*> conn.mgr.userdata
    if manager_obj == NULL:
        return
    manager = <Manager> manager_obj
    py_conn = manager._ensure_connection(conn)
    handler = manager._resolve_handler(py_conn)
    payload = manager._wrap_event_data(ev, ev_data)
    if handler is not None:
        try:
            handler(py_conn, ev, payload)
        except Exception as exc:
            if manager._error_handler is not None:
                try:
                    manager._error_handler(exc)
                except Exception:
                    traceback.print_exc()
            else:
                traceback.print_exc()
    # Always clean up connection on close, even if no handler
    if ev == MG_EV_CLOSE:
        manager._drop_connection(conn)


# JSON utilities
def json_get(data, path: str):
    """Extract a value from JSON by path (e.g., '$.user.name').

    Args:
        data: JSON string or bytes
        path: JSON path (e.g., '$.items[0].id')

    Returns:
        String value at path, or None if not found
    """
    cdef bytes json_b
    if isinstance(data, str):
        json_b = data.encode("utf-8")
    else:
        json_b = bytes(data)
    cdef bytes path_b = path.encode("utf-8")
    cdef mg_str json_str = mg_str_n(json_b, len(json_b))
    cdef mg_str result = mg_json_get_tok(json_str, path_b)
    if result.buf == NULL:
        return None
    return _mg_str_to_text(result)


def json_get_num(data, path: str, default=None):
    """Extract a numeric value from JSON by path.

    Args:
        data: JSON string or bytes
        path: JSON path (e.g., '$.count')
        default: Default value if not found or not a number

    Returns:
        Float value at path, or default if not found
    """
    cdef bytes json_b
    if isinstance(data, str):
        json_b = data.encode("utf-8")
    else:
        json_b = bytes(data)
    cdef bytes path_b = path.encode("utf-8")
    cdef mg_str json_str = mg_str_n(json_b, len(json_b))
    cdef double value
    if mg_json_get_num(json_str, path_b, &value):
        return value
    return default


def json_get_bool(data, path: str, default=None):
    """Extract a boolean value from JSON by path.

    Args:
        data: JSON string or bytes
        path: JSON path (e.g., '$.enabled')
        default: Default value if not found or not a boolean

    Returns:
        Boolean value at path, or default if not found
    """
    cdef bytes json_b
    if isinstance(data, str):
        json_b = data.encode("utf-8")
    else:
        json_b = bytes(data)
    cdef bytes path_b = path.encode("utf-8")
    cdef mg_str json_str = mg_str_n(json_b, len(json_b))
    cdef cbool value = False
    if mg_json_get_bool(json_str, path_b, &value):
        # mg_json_get_bool returns true on success, value contains the actual boolean
        return value != 0
    return default


def json_get_long(data, path: str, default=0):
    """Extract an integer value from JSON by path.

    Args:
        data: JSON string or bytes
        path: JSON path (e.g., '$.id')
        default: Default value if not found or not an integer

    Returns:
        Integer value at path, or default if not found
    """
    cdef bytes json_b
    if isinstance(data, str):
        json_b = data.encode("utf-8")
    else:
        json_b = bytes(data)
    cdef bytes path_b = path.encode("utf-8")
    cdef mg_str json_str = mg_str_n(json_b, len(json_b))
    return mg_json_get_long(json_str, path_b, default)


def json_get_str(data, path: str):
    """Extract a string value from JSON by path (automatically unescapes).

    Args:
        data: JSON string or bytes
        path: JSON path (e.g., '$.message')

    Returns:
        Unescaped string value at path, or None if not found
    """
    cdef bytes json_b
    if isinstance(data, str):
        json_b = data.encode("utf-8")
    else:
        json_b = bytes(data)
    cdef bytes path_b = path.encode("utf-8")
    cdef mg_str json_str = mg_str_n(json_b, len(json_b))
    cdef char *result = mg_json_get_str(json_str, path_b)
    if result == NULL:
        return None
    try:
        return result.decode("utf-8", "surrogateescape")
    finally:
        free(result)


# URL encoding
def url_encode(data: str) -> str:
    """URL-encode a string.

    Args:
        data: String to encode

    Returns:
        URL-encoded string
    """
    cdef bytes data_b = data.encode("utf-8")
    cdef size_t src_len = len(data_b)
    # URL encoding can expand up to 3x (worst case: every byte becomes %XX)
    cdef size_t buf_len = src_len * 3 + 1
    cdef char *buf = <char*>malloc(buf_len)
    cdef size_t result_len

    if buf == NULL:
        raise MemoryError("Failed to allocate buffer for URL encoding")

    try:
        result_len = mg_url_encode(data_b, src_len, buf, buf_len)
        return buf[:result_len].decode("ascii")
    finally:
        free(buf)


# Log level control
def log_set(int level):
    """Set the Mongoose C library log verbosity level.

    Args:
        level: One of MG_LL_NONE (0), MG_LL_ERROR (1), MG_LL_INFO (2),
               MG_LL_DEBUG (3), MG_LL_VERBOSE (4)
    """
    global mg_log_level
    mg_log_level = level


def log_get():
    """Return the current Mongoose C library log verbosity level."""
    return mg_log_level


# Multipart form parsing
def http_parse_multipart(body, offset=0):
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
    cdef bytes body_b
    if isinstance(body, str):
        body_b = body.encode("utf-8")
    else:
        body_b = bytes(body)

    cdef mg_str body_str = mg_str_n(body_b, len(body_b))
    cdef mg_http_part part
    cdef size_t next_offset = mg_http_next_multipart(body_str, offset, &part)

    if next_offset == 0:
        return (0, None)

    part_dict = {
        'name': _mg_str_to_text(part.name),
        'filename': _mg_str_to_text(part.filename),
        'body': _mg_str_to_bytes(part.body),
    }

    return (next_offset, part_dict)

# Timer callback bridge - called from C, needs to acquire GIL
cdef void _timer_callback(void *arg) noexcept with gil:
    """C callback that bridges to Python timer handler."""
    if arg == NULL:
        return
    
    cdef PyObject *py_callback = <PyObject*> arg
    try:
        callback = <object> py_callback
        callback()
    except Exception:
        import traceback
        traceback.print_exc()


cdef class Timer:
    """Wrapper for Mongoose timer.

    Note: The underlying mg_timer is automatically freed by Mongoose when it completes
    (via MG_TIMER_AUTODELETE flag). This class only manages the Python callback reference.
    """
    cdef mg_timer *_timer
    cdef object _callback
    cdef PyObject *_callback_ref

    def __cinit__(self):
        self._timer = NULL
        self._callback = None
        self._callback_ref = NULL

    def __dealloc__(self):
        # Release callback reference (mg_timer is auto-freed by Mongoose)
        if self._callback_ref != NULL:
            Py_DECREF(<object>self._callback_ref)
            self._callback_ref = NULL

    cdef void _set_timer(self, mg_timer *timer, object callback):
        self._timer = timer
        self._callback = callback
        # Keep callback alive
        self._callback_ref = <PyObject*> callback
        Py_INCREF(callback)


# Add timer_add to Manager class - find the Manager.close() method and add before it
