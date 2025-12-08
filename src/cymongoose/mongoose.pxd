from libc.stdint cimport uintptr_t, int64_t, uint64_t, uint32_t, uint16_t, uint8_t, int8_t
from libc.stddef cimport size_t
from libc.stdio cimport FILE
from libcpp cimport bool as cbool

cdef extern from "mongoose.h":
    ctypedef void (*mg_event_handler_t)(mg_connection *, int ev, void *ev_data)

    cdef enum:
        MG_MAX_HTTP_HEADERS = 30
        MG_PATH_MAX = 255
        MG_IO_SIZE = 16384


    cdef enum:
        MG_EV_ERROR
        MG_EV_OPEN
        MG_EV_POLL
        MG_EV_RESOLVE
        MG_EV_CONNECT
        MG_EV_ACCEPT
        MG_EV_TLS_HS
        MG_EV_READ
        MG_EV_WRITE
        MG_EV_CLOSE
        MG_EV_HTTP_HDRS
        MG_EV_HTTP_MSG
        MG_EV_WS_OPEN
        MG_EV_WS_MSG
        MG_EV_WS_CTL
        MG_EV_MQTT_CMD
        MG_EV_MQTT_MSG
        MG_EV_MQTT_OPEN
        MG_EV_SNTP_TIME
        MG_EV_WAKEUP
        MG_EV_USER

    cdef enum:
        WEBSOCKET_OP_CONTINUE = 0
        WEBSOCKET_OP_TEXT = 1
        WEBSOCKET_OP_BINARY = 2
        WEBSOCKET_OP_CLOSE = 8
        WEBSOCKET_OP_PING = 9
        WEBSOCKET_OP_PONG = 10

    cdef struct mg_str:
        char *buf
        size_t len

    cdef struct mg_addr:
        uint8_t ip[16]
        uint16_t port
        uint8_t scope_id
        bint is_ip6

    cdef struct mg_iobuf:
        unsigned char *buf
        size_t size
        size_t len
        size_t align

    cdef struct mg_connection:
        mg_connection *next
        mg_mgr *mgr
        mg_addr loc
        mg_addr rem
        void *fd
        unsigned long id
        mg_iobuf recv
        mg_iobuf send
        mg_iobuf prof
        mg_iobuf rtls
        mg_event_handler_t fn
        void *fn_data
        mg_event_handler_t pfn
        void *pfn_data
        char data[32]
        void *tls
        unsigned int is_listening
        unsigned int is_client
        unsigned int is_accepted
        unsigned int is_resolving
        unsigned int is_arplooking
        unsigned int is_connecting
        unsigned int is_tls
        unsigned int is_tls_hs
        unsigned int is_udp
        unsigned int is_websocket
        unsigned int is_mqtt5
        unsigned int is_hexdumping
        unsigned int is_draining
        unsigned int is_closing
        unsigned int is_full
        unsigned int is_tls_throttled
        unsigned int is_resp
        unsigned int is_readable
        unsigned int is_writable

    cdef struct mg_mgr:
        mg_connection *conns
        void *userdata

    cdef struct mg_http_header:
        mg_str name
        mg_str value

    cdef struct mg_http_message:
        mg_str method
        mg_str uri
        mg_str query
        mg_str proto
        mg_http_header headers[MG_MAX_HTTP_HEADERS]
        mg_str body
        mg_str head
        mg_str message

    cdef struct mg_ws_message:
        mg_str data
        uint8_t flags

    cdef void mg_mgr_init(mg_mgr *mgr) nogil
    cdef void mg_mgr_free(mg_mgr *mgr) nogil
    cdef void mg_mgr_poll(mg_mgr *mgr, int msecs) nogil
    cdef mg_connection *mg_listen(mg_mgr *mgr, const char *url, mg_event_handler_t fn, void *fn_data) nogil
    cdef mg_connection *mg_connect(mg_mgr *mgr, const char *url, mg_event_handler_t fn, void *fn_data) nogil
    cdef bint mg_send(mg_connection *conn, const void *buf, size_t len) nogil
    cdef size_t mg_printf(mg_connection *conn, const char *fmt, ...) nogil
    cdef void mg_close_conn(mg_connection *conn) nogil
    cdef void mg_error(mg_connection *c, const char *fmt, ...) nogil
    cdef void mg_resolve(mg_connection *c, const char *url) nogil
    cdef void mg_resolve_cancel(mg_connection *c) nogil

    cdef mg_connection *mg_http_listen(mg_mgr *mgr, const char *url, mg_event_handler_t fn, void *fn_data) nogil
    cdef mg_connection *mg_http_connect(mg_mgr *mgr, const char *url, mg_event_handler_t fn, void *fn_data) nogil
    cdef void mg_http_reply(mg_connection *conn, int status_code, const char *headers, const char *body_fmt, ...) nogil
    cdef void mg_http_serve_dir(mg_connection *conn, mg_http_message *hm, mg_http_serve_opts *opts) nogil
    cdef mg_str *mg_http_get_header(mg_http_message *hm, const char *name) nogil
    cdef int mg_http_get_var(const mg_str *buf, const char *name, char *dst, size_t dst_len) nogil
    cdef int mg_url_decode(const char *s, size_t n, char *to, size_t to_len, int form) nogil
    cdef int mg_http_parse(const char *s, size_t len, mg_http_message *hm) nogil
    cdef int mg_http_get_request_len(const unsigned char *buf, size_t buf_len) nogil
    cdef void mg_http_printf_chunk(mg_connection *cnn, const char *fmt, ...) nogil
    cdef void mg_http_write_chunk(mg_connection *c, const char *buf, size_t len) nogil
    cdef void mg_http_creds(mg_http_message *hm, char *user, size_t user_len, char *_pass, size_t pass_len) nogil
    cdef long mg_http_upload(mg_connection *c, mg_http_message *hm, mg_fs *fs, const char *dir, size_t max_size) nogil
    cdef void mg_http_bauth(mg_connection *c, const char *user, const char *_pass) nogil
    cdef size_t mg_http_next_multipart(mg_str buf, size_t ofs, mg_http_part *part) nogil
    cdef void mg_http_serve_ssi(mg_connection *c, const char *root, const char *fullpath) nogil
    cdef mg_str mg_http_get_header_var(mg_str s, mg_str v) nogil
    cdef int mg_http_status(mg_http_message *hm) nogil

    cdef mg_connection *mg_ws_connect(mg_mgr *mgr, const char *url, mg_event_handler_t fn, void *fn_data, const char *fmt, ...) nogil
    cdef void mg_ws_upgrade(mg_connection *conn, mg_http_message *hm, const char *fmt, ...) nogil
    cdef size_t mg_ws_send(mg_connection *conn, const void *buf, size_t len, int op) nogil
    cdef size_t mg_ws_printf(mg_connection *conn, int op, const char *fmt, ...) nogil
    cdef size_t mg_ws_wrap(mg_connection *c, size_t len, int op) nogil
    # cdef size_t mg_ws_vprintf(mg_connection *c, int op, const char *fmt, va_list *ap)

    cdef struct mg_tls_opts:
        mg_str ca
        mg_str cert
        mg_str key
        mg_str name
        int skip_verification

    cdef void mg_tls_init(mg_connection *conn, const mg_tls_opts *opts) nogil
    cdef void mg_tls_free(mg_connection *conn) nogil

    cdef struct mg_http_serve_opts:
        const char *root_dir
        const char *ssi_pattern
        const char *extra_headers
        const char *mime_types
        const char *page404
        mg_fs *fs

    cdef struct mg_fs:
        pass

    cdef struct mg_http_part:
        mg_str name
        mg_str filename
        mg_str body

    cdef mg_str mg_str_n(const char *s, size_t n)

    # JSON parsing
    cdef int mg_json_get(mg_str json, const char *path, int *toklen)
    cdef mg_str mg_json_get_tok(mg_str json, const char *path)
    cdef cbool mg_json_get_num(mg_str json, const char *path, double *v)
    cdef cbool mg_json_get_bool(mg_str json, const char *path, cbool *v)
    cdef long mg_json_get_long(mg_str json, const char *path, long dflt)
    cdef char *mg_json_get_str(mg_str json, const char *path)
    cdef char *mg_json_get_hex(mg_str json, const char *path, int *len)
    cdef char *mg_json_get_b64(mg_str json, const char *path, int *len)
    cdef bint mg_json_unescape(mg_str str, char *buf, size_t len)
    cdef size_t mg_json_next(mg_str obj, size_t ofs, mg_str *key, mg_str *val)

    # Additional HTTP functions
    cdef void mg_http_serve_file(mg_connection *conn, mg_http_message *hm, const char *path, mg_http_serve_opts *opts) nogil

    # Wakeup
    cdef bint mg_wakeup(mg_mgr *mgr, unsigned long id, const void *buf, size_t len) nogil
    cdef bint mg_wakeup_init(mg_mgr *mgr) nogil

    # URL encoding
    cdef size_t mg_url_encode(const char *s, size_t n, char *buf, size_t len)

    # Multipart forms
    cdef size_t mg_http_next_multipart(mg_str body, size_t offset, mg_http_part *part)

    # MQTT - Note: 'pass' field renamed to 'password' to avoid Python keyword
    cdef struct mg_mqtt_opts "mg_mqtt_opts":
        mg_str user
        mg_str password "pass"  # Real C name is 'pass'
        mg_str client_id
        mg_str topic
        mg_str message
        uint8_t qos
        uint8_t version
        uint16_t keepalive
        uint16_t retransmit_id
        bint retain
        bint clean

    cdef struct mg_mqtt_message:
        mg_str topic
        mg_str data
        mg_str dgram
        uint16_t id
        uint8_t cmd
        uint8_t qos
        uint8_t ack

    cdef mg_connection *mg_mqtt_connect(mg_mgr *mgr, const char *url, mg_mqtt_opts *opts, mg_event_handler_t fn, void *fn_data) nogil
    cdef mg_connection *mg_mqtt_listen(mg_mgr *mgr, const char *url, mg_event_handler_t fn, void *fn_data) nogil
    cdef void mg_mqtt_login(mg_connection *c, mg_mqtt_opts *opts) nogil
    cdef uint16_t mg_mqtt_pub(mg_connection *c, mg_mqtt_opts *opts) nogil
    cdef void mg_mqtt_sub(mg_connection *c, mg_mqtt_opts *opts) nogil
    cdef void mg_mqtt_ping(mg_connection *c) nogil
    cdef void mg_mqtt_pong(mg_connection *c) nogil
    cdef void mg_mqtt_disconnect(mg_connection *c, mg_mqtt_opts *opts) nogil

    # SNTP (Simple Network Time Protocol)
    cdef mg_connection *mg_sntp_connect(mg_mgr *mgr, const char *url, mg_event_handler_t fn, void *fn_data) nogil
    cdef void mg_sntp_request(mg_connection *c) nogil
    cdef int64_t mg_sntp_parse(const unsigned char *buf, size_t len) nogil

    # Timer API
    cdef struct mg_timer:
        pass

    # Timer function pointer type - callback takes void* argument
    ctypedef void (*mg_timer_fn_t)(void *arg)

    # Timer flags
    cdef enum:
        MG_TIMER_ONCE = 0
        MG_TIMER_REPEAT = 1
        MG_TIMER_RUN_NOW = 2
        MG_TIMER_CALLED = 4
        MG_TIMER_AUTODELETE = 8

    cdef mg_timer *mg_timer_add(mg_mgr *mgr, uint64_t milliseconds, unsigned flags, mg_timer_fn_t fn, void *arg)
    cdef void mg_timer_free(mg_timer **head, mg_timer *timer)
