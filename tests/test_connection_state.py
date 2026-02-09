"""Tests for connection state properties and error handling."""

from cymongoose import MG_EV_ERROR, MG_EV_HTTP_MSG, MG_EV_OPEN, Manager


def test_connection_state_listener():
    """Test connection state flags on a listener."""
    manager = Manager()

    try:
        listener = manager.listen("tcp://127.0.0.1:0")
        manager.poll(10)

        # Listener should not be a client
        assert not listener.is_client
        assert listener.is_listening
        assert not listener.is_udp
        assert not listener.is_websocket
        assert not listener.is_tls
    finally:
        manager.close()


def test_connection_state_client():
    """Test connection state flags on a client connection."""
    manager = Manager()
    client_conn = None

    def handler(conn, ev, data):
        nonlocal client_conn
        if ev == MG_EV_OPEN:
            client_conn = conn

    try:
        # Connect to a non-existent server (connection will be created but not connected)
        manager.connect("tcp://127.0.0.1:9999", handler=handler)
        manager.poll(10)

        # Client connection should have is_client set
        if client_conn:
            assert client_conn.is_client
            assert not client_conn.is_listening
    finally:
        manager.close()


def test_connection_error_method():
    """Test triggering error event with error() method."""
    manager = Manager()
    errors = []

    def handler(conn, ev, data):
        if ev == MG_EV_ERROR:
            errors.append(data)

    try:
        listener = manager.listen("tcp://127.0.0.1:0", handler=handler)
        manager.poll(10)

        # Trigger an error
        listener.error("Test error message")
        manager.poll(10)

        # Error event should have been received
        assert len(errors) > 0
        assert "Test error message" in errors[0]
    finally:
        manager.close()


def test_connection_readable_writable():
    """Test is_readable and is_writable properties."""
    manager = Manager()
    conn_states = []

    def handler(conn, ev, data):
        if ev == MG_EV_HTTP_MSG:
            # Record connection state when message is received
            conn_states.append({"is_readable": conn.is_readable, "is_writable": conn.is_writable})
            conn.reply(200, b"OK")

    try:
        listener = manager.listen("http://127.0.0.1:0", handler=handler)
        manager.poll(10)

        # Simply verify listener properties exist
        # The properties should be False/True depending on state
        assert isinstance(listener.is_readable, bool)
        assert isinstance(listener.is_writable, bool)

    finally:
        manager.close()


def test_connection_id_property():
    """Test connection ID property."""
    manager = Manager()

    try:
        listener = manager.listen("tcp://127.0.0.1:0")
        manager.poll(10)

        # Connection ID should be non-zero
        assert listener.id > 0
    finally:
        manager.close()


def test_is_udp_flag():
    """Test UDP connection flag."""
    manager = Manager()

    try:
        # Create a UDP listener
        listener = manager.listen("udp://127.0.0.1:0")
        manager.poll(10)

        # Should be marked as UDP
        assert listener.is_udp
        assert not listener.is_client
    finally:
        manager.close()
