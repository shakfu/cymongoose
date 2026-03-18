"""Tests for MQTT pub/sub round-trip and MqttMessage properties.

Uses a minimal broker that tracks subscriptions and routes published
messages to matching subscribers.
"""

import threading
import time

from cymongoose import (
    MG_EV_CLOSE,
    MG_EV_MQTT_CMD,
    MG_EV_MQTT_MSG,
    MG_EV_MQTT_OPEN,
    Manager,
)


class MiniBroker:
    """Minimal MQTT broker for testing pub/sub round-trips.

    Tracks subscriber connections and forwards all PUBLISH messages to
    every subscriber.  Mongoose's MQTT parser does not expose the topic
    from SUBSCRIBE packets, so this broker uses a broadcast model --
    the subscriber-side handler is responsible for filtering by topic.
    """

    def __init__(self):
        self.subscribers = []  # connections that sent SUBSCRIBE
        self.manager = Manager(self._handler)
        self._stop = threading.Event()
        self._thread = None
        self.port = 0

    def _handler(self, conn, ev, data):
        if ev == MG_EV_MQTT_CMD:
            cmd = data.cmd
            if cmd == 1:  # CONNECT -- send CONNACK
                conn.send(b"\x20\x02\x00\x00")
            elif cmd == 8:  # SUBSCRIBE -- track connection
                self.subscribers.append(conn)
            elif cmd == 3:  # PUBLISH -- broadcast to all subscribers
                topic = data.topic
                payload = data.data
                for sub_conn in self.subscribers:
                    if not sub_conn.is_closing:
                        sub_conn.mqtt_pub(topic, payload, qos=0)
        elif ev == MG_EV_CLOSE:
            self.subscribers = [c for c in self.subscribers if c.id != conn.id]

    def start(self):
        listener = self.manager.mqtt_listen("mqtt://127.0.0.1:0")
        self.port = listener.local_addr[1]
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def _run(self):
        while not self._stop.is_set():
            self.manager.poll(50)

    def stop(self):
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=2)
        self.manager.close()


def _run_pubsub_test(topic, payloads, sub_handler_factory, extra_setup=None):
    """Helper: set up broker + subscriber + publisher, return collected results.

    The subscriber runs in a background thread so it can receive messages
    forwarded by the broker while the publisher is sending.
    """
    broker = MiniBroker()
    broker.start()

    results = []
    sub_ready = threading.Event()
    sub_stop = threading.Event()

    def sub_handler(conn, ev, data):
        sub_handler_factory(conn, ev, data, results, sub_ready)

    try:
        # Subscriber in background thread
        sub_mgr = Manager(sub_handler)
        sub_mgr.mqtt_connect(
            f"mqtt://127.0.0.1:{broker.port}",
            clean_session=True,
            keepalive=10,
        )
        sub_thread = threading.Thread(
            target=lambda: _poll_until(sub_mgr, sub_stop),
            daemon=True,
        )
        sub_thread.start()

        assert sub_ready.wait(timeout=3), "Subscriber did not connect"

        if extra_setup:
            extra_setup(broker)

        # Publisher from main thread
        pub_mgr = Manager()
        pub_conn = pub_mgr.mqtt_connect(
            f"mqtt://127.0.0.1:{broker.port}",
            clean_session=True,
            keepalive=10,
        )
        for _ in range(10):
            pub_mgr.poll(50)

        for payload in payloads:
            pub_conn.mqtt_pub(topic, payload, qos=0)
        for _ in range(10):
            pub_mgr.poll(50)

        # Wait for delivery
        deadline = time.monotonic() + 3
        while time.monotonic() < deadline:
            if len(results) >= len(payloads):
                break
            time.sleep(0.05)

        pub_mgr.close()
        sub_stop.set()
        sub_thread.join(timeout=2)
        sub_mgr.close()
    finally:
        broker.stop()

    return results


class TestMqttPubSubRoundTrip:
    """Verify end-to-end MQTT message delivery."""

    def test_publish_and_receive(self):
        """Client subscribes, another publishes, subscriber receives."""

        def handler(conn, ev, data, results, ready):
            if ev == MG_EV_MQTT_OPEN:
                conn.mqtt_sub("test/hello", qos=0)
                ready.set()
            elif ev == MG_EV_MQTT_MSG:
                results.append(
                    {
                        "topic": data.topic,
                        "data": data.data,
                        "text": data.text,
                    }
                )

        results = _run_pubsub_test("test/hello", ["world"], handler)

        assert len(results) == 1
        assert results[0]["topic"] == "test/hello"
        assert results[0]["data"] == b"world"
        assert results[0]["text"] == "world"

    def test_binary_payload(self):
        """Binary payloads are delivered intact."""
        payload = bytes(range(256))

        def handler(conn, ev, data, results, ready):
            if ev == MG_EV_MQTT_OPEN:
                conn.mqtt_sub("bin/topic", qos=0)
                ready.set()
            elif ev == MG_EV_MQTT_MSG:
                results.append(data.data)

        results = _run_pubsub_test("bin/topic", [payload], handler)

        assert len(results) == 1
        assert results[0] == payload

    def test_multiple_messages(self):
        """Multiple messages on the same topic are all delivered."""

        def handler(conn, ev, data, results, ready):
            if ev == MG_EV_MQTT_OPEN:
                conn.mqtt_sub("multi/topic", qos=0)
                ready.set()
            elif ev == MG_EV_MQTT_MSG:
                results.append(data.text)

        msgs = [f"msg-{i}" for i in range(5)]
        results = _run_pubsub_test("multi/topic", msgs, handler)

        assert results == msgs

    def test_topic_filtering_in_subscriber(self):
        """Subscriber can filter by topic using MqttMessage.topic."""

        def handler(conn, ev, data, results, ready):
            if ev == MG_EV_MQTT_OPEN:
                conn.mqtt_sub("yes/topic", qos=0)
                ready.set()
            elif ev == MG_EV_MQTT_MSG:
                # Client-side filtering: only collect matching topic
                if data.topic == "yes/topic":
                    results.append(data.text)

        # The MiniBroker broadcasts all publishes to all subscribers,
        # so the subscriber must filter by topic -- standard MQTT pattern.
        results = _run_pubsub_test(
            "yes/topic",
            ["correct"],
            handler,
        )
        assert results == ["correct"]


class TestMqttMessageProperties:
    """Verify MqttMessage view properties on the broker side."""

    def test_cmd_property_on_broker(self):
        """Broker handler receives cmd=3 (PUBLISH) for published messages."""
        commands_seen = []

        def broker_handler(conn, ev, data):
            if ev == MG_EV_MQTT_CMD:
                commands_seen.append(data.cmd)
                if data.cmd == 1:  # CONNECT -> CONNACK
                    conn.send(b"\x20\x02\x00\x00")

        broker_mgr = Manager(broker_handler)
        listener = broker_mgr.mqtt_listen("mqtt://127.0.0.1:0")
        port = listener.local_addr[1]

        stop = threading.Event()
        t = threading.Thread(target=lambda: _poll_until(broker_mgr, stop), daemon=True)
        t.start()

        try:
            client = Manager()
            conn = client.mqtt_connect(
                f"mqtt://127.0.0.1:{port}",
                clean_session=True,
                keepalive=10,
            )
            for _ in range(10):
                client.poll(50)

            conn.mqtt_pub("t", "msg", qos=0)
            conn.mqtt_sub("t", qos=0)
            for _ in range(10):
                client.poll(50)
            time.sleep(0.2)

            # cmd 1=CONNECT, 3=PUBLISH, 8=SUBSCRIBE
            assert 1 in commands_seen  # CONNECT
            assert 3 in commands_seen  # PUBLISH
            assert 8 in commands_seen  # SUBSCRIBE

            client.close()
        finally:
            stop.set()
            t.join(timeout=2)
            broker_mgr.close()

    def test_mqtt_open_event(self):
        """Client receives MG_EV_MQTT_OPEN with status code on connect."""

        def broker_handler(conn, ev, data):
            if ev == MG_EV_MQTT_CMD and data.cmd == 1:
                conn.send(b"\x20\x02\x00\x00")

        broker_mgr = Manager(broker_handler)
        listener = broker_mgr.mqtt_listen("mqtt://127.0.0.1:0")
        port = listener.local_addr[1]

        stop = threading.Event()
        t = threading.Thread(target=lambda: _poll_until(broker_mgr, stop), daemon=True)
        t.start()

        open_status = []

        def client_handler(conn, ev, data):
            if ev == MG_EV_MQTT_OPEN:
                open_status.append(data)

        try:
            client = Manager(client_handler)
            client.mqtt_connect(
                f"mqtt://127.0.0.1:{port}",
                clean_session=True,
                keepalive=10,
            )
            for _ in range(20):
                client.poll(50)
                if open_status:
                    break

            assert len(open_status) == 1
            assert isinstance(open_status[0], int)

            client.close()
        finally:
            stop.set()
            t.join(timeout=2)
            broker_mgr.close()


def _poll_until(mgr, stop_event):
    while not stop_event.is_set():
        mgr.poll(50)
