"""Tests for advanced MQTT features."""

import pytest
import time
from cymongoose import Manager, MG_EV_MQTT_OPEN, MG_EV_MQTT_MSG, MG_EV_CLOSE


def test_mqtt_disconnect_method_exists():
    """Test that mqtt_disconnect method exists."""
    manager = Manager()

    try:
        # Create a connection (doesn't need to actually connect for method check)
        conn = manager.listen("tcp://127.0.0.1:0")
        manager.poll(10)

        # Method should exist
        assert hasattr(conn, "mqtt_disconnect")
        assert callable(conn.mqtt_disconnect)

        # Should be callable without error (even if not MQTT connection)
        conn.mqtt_disconnect()
        manager.poll(10)
    finally:
        manager.close()


def test_mqtt_ping_method_exists():
    """Test that mqtt_ping method exists."""
    manager = Manager()

    try:
        conn = manager.listen("tcp://127.0.0.1:0")
        manager.poll(10)

        assert hasattr(conn, "mqtt_ping")
        assert callable(conn.mqtt_ping)

        conn.mqtt_ping()
        manager.poll(10)
    finally:
        manager.close()


def test_mqtt_pong_method_exists():
    """Test that mqtt_pong method exists."""
    manager = Manager()

    try:
        conn = manager.listen("tcp://127.0.0.1:0")
        manager.poll(10)

        assert hasattr(conn, "mqtt_pong")
        assert callable(conn.mqtt_pong)

        conn.mqtt_pong()
        manager.poll(10)
    finally:
        manager.close()


def test_mqtt_pub_method_exists():
    """Test that mqtt_pub method exists."""
    manager = Manager()

    try:
        conn = manager.listen("tcp://127.0.0.1:0")
        manager.poll(10)

        assert hasattr(conn, "mqtt_pub")
        assert callable(conn.mqtt_pub)
    finally:
        manager.close()


def test_mqtt_sub_method_exists():
    """Test that mqtt_sub method exists."""
    manager = Manager()

    try:
        conn = manager.listen("tcp://127.0.0.1:0")
        manager.poll(10)

        assert hasattr(conn, "mqtt_sub")
        assert callable(conn.mqtt_sub)
    finally:
        manager.close()


def test_mqtt_connect_method_exists():
    """Test that Manager has mqtt_connect method."""
    manager = Manager()

    try:
        assert hasattr(manager, "mqtt_connect")
        assert callable(manager.mqtt_connect)
    finally:
        manager.close()


def test_mqtt_listen_method_exists():
    """Test that Manager has mqtt_listen method."""
    manager = Manager()

    try:
        assert hasattr(manager, "mqtt_listen")
        assert callable(manager.mqtt_listen)
    finally:
        manager.close()


def test_mqtt_disconnect_no_crash():
    """Test that mqtt_disconnect doesn't crash on non-MQTT connection."""
    manager = Manager()

    try:
        # HTTP listener (not MQTT)
        conn = manager.listen("http://127.0.0.1:0")
        manager.poll(10)

        # Should not crash even on HTTP connection
        conn.mqtt_disconnect()
        manager.poll(10)

        assert conn.is_listening
    finally:
        manager.close()


def test_mqtt_ping_pong_sequence():
    """Test mqtt_ping and mqtt_pong can be called in sequence."""
    manager = Manager()

    try:
        conn = manager.listen("tcp://127.0.0.1:0")
        manager.poll(10)

        # Should be able to call both
        conn.mqtt_ping()
        manager.poll(10)
        conn.mqtt_pong()
        manager.poll(10)

        assert conn.is_listening
    finally:
        manager.close()


def test_mqtt_pub_basic_call():
    """Test mqtt_pub can be called with topic and message."""
    manager = Manager()

    try:
        conn = manager.listen("tcp://127.0.0.1:0")
        manager.poll(10)

        # Should be callable with topic and message and return a message ID
        msg_id = conn.mqtt_pub("test/topic", "test message")
        manager.poll(10)

        assert isinstance(msg_id, int)
    finally:
        manager.close()


def test_mqtt_sub_basic_call():
    """Test mqtt_sub can be called with topic."""
    manager = Manager()

    try:
        conn = manager.listen("tcp://127.0.0.1:0")
        manager.poll(10)

        # Should be callable with topic
        conn.mqtt_sub("test/topic")
        manager.poll(10)

        assert conn.is_listening
    finally:
        manager.close()
