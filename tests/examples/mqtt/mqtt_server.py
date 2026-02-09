#!/usr/bin/env python3
"""Example MQTT broker/server.

This example demonstrates:
1. Listen for MQTT client connections
2. Handle CONNECT, SUBSCRIBE, PUBLISH, PINGREQ commands
3. Maintain subscription list
4. Route published messages to subscribers
5. Topic matching with wildcards

Usage:
    python mqtt_server.py [-l LISTEN_URL]

Example:
    python mqtt_server.py -l mqtt://0.0.0.0:1883

    # Test with mosquitto clients:
    mosquitto_sub -h localhost -t foo -t bar
    mosquitto_pub -h localhost -t foo -m hello

Translation from C tutorial: thirdparty/mongoose/tutorials/mqtt/mqtt-server/main.c
"""

import argparse
import signal

from cymongoose import (
    MG_EV_ACCEPT,
    MG_EV_CLOSE,
    MG_EV_MQTT_CMD,
    Manager,
)

# Default configuration
DEFAULT_LISTEN = "mqtt://0.0.0.0:1883"

# Global state
shutdown_requested = False
subscriptions = []  # List of (connection, topic, qos) tuples


def signal_handler(sig, frame):
    """Handle shutdown signals (Ctrl+C, SIGTERM)."""
    global shutdown_requested
    shutdown_requested = True


def topic_match(msg_topic, sub_topic):
    """Match MQTT topic with wildcards.

    MQTT wildcards:
    - '+' matches a single level
    - '#' matches multiple levels

    Args:
        msg_topic: Published message topic (str)
        sub_topic: Subscription topic pattern (str)

    Returns:
        bool: True if topics match
    """
    # Simple wildcard matching
    # Convert '+' to single-level wildcard, '#' to multi-level wildcard
    msg_parts = msg_topic.split("/")
    sub_parts = sub_topic.split("/")

    # '#' must be last and matches everything after
    if "#" in sub_parts:
        idx = sub_parts.index("#")
        if idx != len(sub_parts) - 1:
            return False  # '#' must be last
        sub_parts = sub_parts[:idx]
        msg_parts = msg_parts[:idx]

    if len(msg_parts) != len(sub_parts):
        return False

    for mp, sp in zip(msg_parts, sub_parts):
        if sp != "+" and sp != mp:
            return False

    return True


def mqtt_ev_handler(conn, ev, data):
    """MQTT server event handler.

    Args:
        conn: Connection object
        ev: Event type
        data: Event data
    """
    if ev == MG_EV_ACCEPT:
        # New client connected
        print(f"[{conn.id}] CLIENT CONNECTED")

    elif ev == MG_EV_MQTT_CMD:
        # MQTT command received
        mm = data  # MqttMessage object

        # MQTT command constants (from Mongoose)
        # MQTT_CMD_CONNECT = 1
        # MQTT_CMD_SUBSCRIBE = 8
        # MQTT_CMD_PUBLISH = 3
        # MQTT_CMD_PINGREQ = 12

        cmd = mm.cmd
        print(f"[{conn.id}] MQTT_CMD: {cmd} qos={mm.qos}")

        if cmd == 1:  # MQTT_CMD_CONNECT
            # Client connecting - send CONNACK
            # In Python, we just log it; Mongoose handles the protocol
            print(f"[{conn.id}] CONNECT received")

        elif cmd == 8:  # MQTT_CMD_SUBSCRIBE
            # Client subscribing
            try:
                topic = mm.topic
                qos = mm.qos

                # Add subscription
                subscriptions.append((conn, topic, qos))
                print(f"[{conn.id}] SUBSCRIBE to [{topic}] qos={qos}")

                # Note: In the C version, they parse multiple topics from the packet
                # and send SUBACK manually. In Python, Mongoose handles the protocol
                # so we just track the subscription.

            except Exception as e:
                print(f"[{conn.id}] SUBSCRIBE error: {e}")

        elif cmd == 3:  # MQTT_CMD_PUBLISH
            # Client published message - route to subscribers
            try:
                pub_topic = mm.topic
                pub_data = mm.data.decode("utf-8", errors="ignore")
                print(f"[{conn.id}] PUBLISH [{pub_topic}] -> [{pub_data}]")

                # Route to matching subscriptions
                for sub_conn, sub_topic, sub_qos in subscriptions:
                    if topic_match(pub_topic, sub_topic):
                        try:
                            # Publish to subscriber
                            sub_conn.mqtt_pub(pub_topic, mm.data, qos=sub_qos)
                            print(f"  -> Forwarding to [{sub_conn.id}]")
                        except RuntimeError as e:
                            # Connection might be closed
                            print(f"  -> Failed to forward to [{sub_conn.id}]: {e}")

            except Exception as e:
                print(f"[{conn.id}] PUBLISH error: {e}")

        elif cmd == 12:  # MQTT_CMD_PINGREQ
            # Client ping - send pong
            print(f"[{conn.id}] PINGREQ -> PINGRESP")
            try:
                conn.mqtt_pong()
            except RuntimeError as e:
                print(f"[{conn.id}] PONG failed: {e}")

    elif ev == MG_EV_CLOSE:
        # Client disconnected - remove subscriptions
        print(f"[{conn.id}] CLIENT DISCONNECTED")

        # Remove all subscriptions for this connection (using list comprehension on global)
        old_count = len(subscriptions)
        removed_subscriptions = [(c, t, q) for c, t, q in subscriptions if c != conn]
        subscriptions[:] = removed_subscriptions  # Modify list in place
        removed = old_count - len(subscriptions)
        if removed > 0:
            print(f"[{conn.id}] REMOVED {removed} subscription(s)")


def main():
    """Main function."""
    global shutdown_requested

    # Parse command-line arguments
    parser = argparse.ArgumentParser(description="MQTT broker/server example")
    parser.add_argument(
        "-l", "--listen", default=DEFAULT_LISTEN, help=f"Listen URL (default: {DEFAULT_LISTEN})"
    )

    args = parser.parse_args()

    # Register signal handlers
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    # Create manager
    manager = Manager(mqtt_ev_handler)

    try:
        # Start listening
        manager.mqtt_listen(args.listen)
        print(f"MQTT Broker started on {args.listen}")
        print("Press Ctrl+C to exit")
        print()
        print("Test with mosquitto clients:")
        print("  mosquitto_sub -h localhost -t foo -t bar")
        print("  mosquitto_pub -h localhost -t foo -m hello")

        # Event loop
        while not shutdown_requested:
            manager.poll(100)

        print("\nShutting down...")

    finally:
        manager.close()
        print("Broker stopped cleanly")


if __name__ == "__main__":
    main()
