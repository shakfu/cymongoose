"""Tests for exported constants."""

from cymongoose import (
    MG_EV_ACCEPT,
    MG_EV_CLOSE,
    MG_EV_CONNECT,
    MG_EV_ERROR,
    MG_EV_HTTP_HDRS,
    MG_EV_HTTP_MSG,
    MG_EV_OPEN,
    MG_EV_POLL,
    MG_EV_READ,
    MG_EV_RESOLVE,
    MG_EV_TLS_HS,
    MG_EV_USER,
    MG_EV_WAKEUP,
    MG_EV_WRITE,
    MG_EV_WS_CTL,
    MG_EV_WS_MSG,
    MG_EV_WS_OPEN,
    WEBSOCKET_OP_BINARY,
    WEBSOCKET_OP_PING,
    WEBSOCKET_OP_PONG,
    WEBSOCKET_OP_TEXT,
)


class TestConstants:
    """Test that constants are properly exported."""

    def test_event_constants_are_integers(self):
        """Test all event constants are integers."""
        constants = [
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
            MG_EV_WAKEUP,
            MG_EV_USER,
        ]

        for const in constants:
            assert isinstance(const, int)

    def test_websocket_constants_are_integers(self):
        """Test WebSocket op constants are integers."""
        constants = [
            WEBSOCKET_OP_TEXT,
            WEBSOCKET_OP_BINARY,
            WEBSOCKET_OP_PING,
            WEBSOCKET_OP_PONG,
        ]

        for const in constants:
            assert isinstance(const, int)

    def test_event_constants_are_unique(self):
        """Test event constants have unique values."""
        constants = [
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
            MG_EV_WAKEUP,
            MG_EV_USER,
        ]

        assert len(constants) == len(set(constants))

    def test_websocket_op_text_is_one(self):
        """Test WEBSOCKET_OP_TEXT equals 1 (per WebSocket spec)."""
        assert WEBSOCKET_OP_TEXT == 1

    def test_websocket_op_binary_is_two(self):
        """Test WEBSOCKET_OP_BINARY equals 2 (per WebSocket spec)."""
        assert WEBSOCKET_OP_BINARY == 2
