#!/usr/bin/env python3
"""
Comprehensive tests for MQTT client and server examples.

Tests the interaction between MQTT client and broker.
"""

import sys
import time
import threading
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from cymongoose import (
    Manager,
    MG_EV_ACCEPT,
    MG_EV_MQTT_CMD,
    MG_EV_MQTT_OPEN,
    MG_EV_MQTT_MSG,
    MG_EV_CLOSE,
)


def test_mqtt_broker_basic():
    """Test basic MQTT broker functionality - broker can listen and receive connections."""
    client_connected = threading.Event()

    def broker_handler(conn, ev, data):
        if ev == MG_EV_ACCEPT:
            # Client TCP connection accepted
            client_connected.set()

    # Start broker
    broker = Manager(broker_handler)
    listener = broker.mqtt_listen("mqtt://127.0.0.1:0")
    port = listener.local_addr[1]

    stop = threading.Event()

    def broker_loop():
        while not stop.is_set():
            broker.poll(50)

    broker_thread = threading.Thread(target=broker_loop, daemon=True)
    broker_thread.start()
    time.sleep(0.1)

    try:
        # Connect client (TCP connection only, MQTT handshake may not complete
        # since we don't implement full broker protocol in this test)
        client = Manager()
        client_conn = client.mqtt_connect(
            f"mqtt://127.0.0.1:{port}", clean_session=True, keepalive=5
        )

        # Poll both to allow TCP connection
        for _ in range(20):
            client.poll(50)
            if client_connected.is_set():
                break
            time.sleep(0.05)

        # Verify broker received the TCP connection
        assert client_connected.is_set(), "Broker should receive TCP connection"

        client.close()

    finally:
        stop.set()
        time.sleep(0.1)
        broker.close()


def test_mqtt_client_can_publish():
    """Test that MQTT client can publish messages (API test)."""
    # This tests the client API works, not full broker functionality
    broker = Manager()
    listener = broker.mqtt_listen("mqtt://127.0.0.1:0")
    port = listener.local_addr[1]

    stop = threading.Event()

    def broker_loop():
        while not stop.is_set():
            broker.poll(50)

    broker_thread = threading.Thread(target=broker_loop, daemon=True)
    broker_thread.start()
    time.sleep(0.1)

    try:
        # Client can connect and call publish methods
        client = Manager()
        client_conn = client.mqtt_connect(
            f"mqtt://127.0.0.1:{port}", clean_session=True, keepalive=5
        )

        # Poll to establish connection
        for _ in range(10):
            client.poll(50)
            time.sleep(0.05)

        # Test that publish methods work without crashing
        client_conn.mqtt_pub("test/topic", "Hello MQTT", qos=0)
        client_conn.mqtt_pub("test/topic", b"Binary data", qos=1)
        client_conn.mqtt_pub("test/topic2", "Another message", qos=2)

        # Poll to send messages
        for _ in range(10):
            client.poll(50)
            time.sleep(0.05)

        assert client_conn.id > 0

        client.close()

    finally:
        stop.set()
        time.sleep(0.1)
        broker.close()


def test_mqtt_client_can_subscribe():
    """Test that MQTT client can subscribe to topics (API test)."""
    # This tests the client API works
    broker = Manager()
    listener = broker.mqtt_listen("mqtt://127.0.0.1:0")
    port = listener.local_addr[1]

    stop = threading.Event()

    def broker_loop():
        while not stop.is_set():
            broker.poll(50)

    broker_thread = threading.Thread(target=broker_loop, daemon=True)
    broker_thread.start()
    time.sleep(0.1)

    try:
        # Client can connect and call subscribe methods
        client = Manager()
        client_conn = client.mqtt_connect(
            f"mqtt://127.0.0.1:{port}", clean_session=True, keepalive=5
        )

        # Poll to establish connection
        for _ in range(10):
            client.poll(50)
            time.sleep(0.05)

        # Test that subscribe methods work without crashing
        client_conn.mqtt_sub("test/topic", qos=0)
        client_conn.mqtt_sub("test/+/wildcard", qos=1)
        client_conn.mqtt_sub("test/#", qos=2)

        # Poll to send subscriptions
        for _ in range(10):
            client.poll(50)
            time.sleep(0.05)

        assert client_conn.id > 0

        client.close()

    finally:
        stop.set()
        time.sleep(0.1)
        broker.close()


def test_mqtt_ping_pong():
    """Test MQTT ping/pong API methods."""
    # Test that ping/pong methods work without crashing
    broker = Manager()
    listener = broker.mqtt_listen("mqtt://127.0.0.1:0")
    port = listener.local_addr[1]

    stop = threading.Event()

    def broker_loop():
        while not stop.is_set():
            broker.poll(50)

    broker_thread = threading.Thread(target=broker_loop, daemon=True)
    broker_thread.start()
    time.sleep(0.1)

    try:
        # Client can call ping methods
        client = Manager()
        client_conn = client.mqtt_connect(
            f"mqtt://127.0.0.1:{port}", clean_session=True, keepalive=5
        )

        # Poll to establish connection
        for _ in range(10):
            client.poll(50)
            time.sleep(0.05)

        # Test ping method works
        client_conn.mqtt_ping()

        # Poll to send ping
        for _ in range(10):
            client.poll(50)
            time.sleep(0.05)

        assert client_conn.id > 0

        client.close()

    finally:
        stop.set()
        time.sleep(0.1)
        broker.close()


def test_mqtt_clean_session():
    """Test MQTT clean session flag."""

    def broker_handler(conn, ev, data):
        pass

    # Start broker
    broker = Manager(broker_handler)
    listener = broker.mqtt_listen("mqtt://127.0.0.1:0")
    port = listener.local_addr[1]

    stop = threading.Event()

    def broker_loop():
        while not stop.is_set():
            broker.poll(50)

    broker_thread = threading.Thread(target=broker_loop, daemon=True)
    broker_thread.start()
    time.sleep(0.1)

    try:
        # Test with clean_session=True
        client1 = Manager()
        conn1 = client1.mqtt_connect(f"mqtt://127.0.0.1:{port}", clean_session=True, keepalive=5)

        for _ in range(20):
            client1.poll(50)
            time.sleep(0.05)

        client1.close()

        # Test with clean_session=False
        client2 = Manager()
        conn2 = client2.mqtt_connect(f"mqtt://127.0.0.1:{port}", clean_session=False, keepalive=5)

        for _ in range(20):
            client2.poll(50)
            time.sleep(0.05)

        client2.close()

        # Both connection variants created successfully
        assert conn1 is not None
        assert conn2 is not None

    finally:
        stop.set()
        time.sleep(0.1)
        broker.close()


def test_mqtt_qos_levels():
    """Test different QoS levels in publish API."""
    # Test that all QoS levels work in the API
    broker = Manager()
    listener = broker.mqtt_listen("mqtt://127.0.0.1:0")
    port = listener.local_addr[1]

    stop = threading.Event()

    def broker_loop():
        while not stop.is_set():
            broker.poll(50)

    broker_thread = threading.Thread(target=broker_loop, daemon=True)
    broker_thread.start()
    time.sleep(0.1)

    try:
        # Client can publish with different QoS levels
        client = Manager()
        client_conn = client.mqtt_connect(
            f"mqtt://127.0.0.1:{port}", clean_session=True, keepalive=5
        )

        # Poll to establish connection
        for _ in range(10):
            client.poll(50)
            time.sleep(0.05)

        # Test all QoS levels work without crashing
        client_conn.mqtt_pub("test/qos0", "QoS 0 message", qos=0)
        client_conn.mqtt_pub("test/qos1", "QoS 1 message", qos=1)
        client_conn.mqtt_pub("test/qos2", "QoS 2 message", qos=2)

        # Poll to send messages
        for _ in range(10):
            client.poll(50)
            time.sleep(0.05)

        assert client_conn.id > 0

        client.close()

    finally:
        stop.set()
        time.sleep(0.1)
        broker.close()


def test_mqtt_topic_matching():
    """Test MQTT topic wildcard matching."""
    from tests.examples.mqtt.mqtt_server import topic_match

    # Exact match
    assert topic_match("test/topic", "test/topic")

    # Single-level wildcard '+'
    assert topic_match("test/topic", "test/+")
    assert topic_match("test/topic", "+/topic")
    assert topic_match("test/topic", "+/+")
    assert not topic_match("test/topic/sub", "test/+")

    # Multi-level wildcard '#'
    assert topic_match("test/topic", "test/#")
    assert topic_match("test/topic/sub", "test/#")
    assert topic_match("test/topic/sub/deep", "test/#")
    assert topic_match("test", "#")

    # No match
    assert not topic_match("test/topic", "other/topic")
    assert not topic_match("test/topic", "test/other")


if __name__ == "__main__":
    # Run tests
    test_mqtt_broker_basic()
    print("[x] test_mqtt_broker_basic")

    test_mqtt_client_can_publish()
    print("[x] test_mqtt_client_can_publish")

    test_mqtt_client_can_subscribe()
    print("[x] test_mqtt_client_can_subscribe")

    test_mqtt_ping_pong()
    print("[x] test_mqtt_ping_pong")

    test_mqtt_clean_session()
    print("[x] test_mqtt_clean_session")

    test_mqtt_qos_levels()
    print("[x] test_mqtt_qos_levels")

    test_mqtt_topic_matching()
    print("[x] test_mqtt_topic_matching")

    print("\nAll MQTT tests passed!")
