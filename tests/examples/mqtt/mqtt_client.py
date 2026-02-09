#!/usr/bin/env python3
"""Example MQTT client.

This example demonstrates:
1. Connect to an MQTT broker
2. Subscribe to a topic
3. Receive and echo messages
4. Timer-based reconnection logic
5. Periodic ping
6. Last will message

Usage:
    python mqtt_client.py [-u URL] [-p PUB_TOPIC] [-s SUB_TOPIC]

Example:
    python mqtt_client.py -u mqtt://broker.hivemq.com:1883 -s mg/123/rx -p mg/123/tx

Translation from C tutorial: thirdparty/mongoose/tutorials/mqtt/mqtt-client/main.c
"""

import argparse
import signal

from cymongoose import (
    MG_EV_CLOSE,
    MG_EV_CONNECT,
    MG_EV_ERROR,
    MG_EV_MQTT_CMD,
    MG_EV_MQTT_MSG,
    MG_EV_MQTT_OPEN,
    MG_EV_OPEN,
    Manager,
)

# Default configuration
DEFAULT_URL = "mqtt://broker.hivemq.com:1883"
DEFAULT_SUB_TOPIC = "mg/123/rx"
DEFAULT_PUB_TOPIC = "mg/123/tx"
DEFAULT_QOS = 1

# Global state
mqtt_conn = None
shutdown_requested = False


def signal_handler(sig, frame):
    """Handle shutdown signals (Ctrl+C, SIGTERM)."""
    global shutdown_requested
    shutdown_requested = True


def subscribe(conn, topic, qos):
    """Subscribe to an MQTT topic.

    Args:
        conn: Connection object
        topic: Topic to subscribe to
        qos: Quality of service level
    """
    conn.mqtt_sub(topic, qos=qos)
    print(f"[{conn.id}] SUBSCRIBED to {topic}")


def publish(conn, topic, message, qos):
    """Publish an MQTT message.

    Args:
        conn: Connection object
        topic: Topic to publish to
        message: Message payload
        qos: Quality of service level
    """
    conn.mqtt_pub(topic, message, qos=qos)
    print(f"[{conn.id}] PUBLISHED {topic} -> {message}")


def mqtt_ev_handler(conn, ev, data, config):
    """MQTT event handler.

    Args:
        conn: Connection object
        ev: Event type
        data: Event data
        config: Client configuration dict
    """
    global mqtt_conn

    if ev == MG_EV_OPEN:
        print(f"[{conn.id}] CREATED")

    elif ev == MG_EV_CONNECT:
        # TLS initialization would happen here if needed
        pass

    elif ev == MG_EV_ERROR:
        print(f"[{conn.id}] ERROR: {data}")

    elif ev == MG_EV_MQTT_OPEN:
        # MQTT connection established
        print(f"[{conn.id}] CONNECTED to {config['url']}")
        subscribe(conn, config["sub_topic"], config["qos"])

    elif ev == MG_EV_MQTT_MSG:
        # Received MQTT message - echo it back
        mm = data  # MqttMessage object
        response = f"Got {mm.topic} -> {mm.data.decode('utf-8', errors='ignore')}"
        publish(conn, config["pub_topic"], response, config["qos"])

    elif ev == MG_EV_MQTT_CMD:
        # MQTT command received
        mm = data  # MqttMessage object
        # In C, MQTT_CMD_PINGREQ = 12, but we don't have direct access to constants
        # The handler responds automatically in most cases
        pass

    elif ev == MG_EV_CLOSE:
        print(f"[{conn.id}] CLOSED")
        mqtt_conn = None


def timer_callback(manager, config):
    """Timer callback for reconnection and ping.

    Args:
        manager: Manager object
        config: Client configuration dict
    """
    global mqtt_conn

    if mqtt_conn is None:
        # Reconnect
        print(f"Connecting to {config['url']}...")
        mqtt_conn = manager.mqtt_connect(
            config["url"],
            handler=lambda c, e, d: mqtt_ev_handler(c, e, d, config),
            clean_session=True,
            keepalive=config["keepalive"],
        )
    else:
        # Send ping
        try:
            mqtt_conn.mqtt_ping()
        except RuntimeError:
            # Connection might have closed
            mqtt_conn = None


def main():
    """Main function."""
    global shutdown_requested

    # Parse command-line arguments
    parser = argparse.ArgumentParser(description="MQTT client example")
    parser.add_argument(
        "-u", "--url", default=DEFAULT_URL, help=f"MQTT broker URL (default: {DEFAULT_URL})"
    )
    parser.add_argument(
        "-p",
        "--pub-topic",
        default=DEFAULT_PUB_TOPIC,
        help=f"Publish topic (default: {DEFAULT_PUB_TOPIC})",
    )
    parser.add_argument(
        "-s",
        "--sub-topic",
        default=DEFAULT_SUB_TOPIC,
        help=f"Subscribe topic (default: {DEFAULT_SUB_TOPIC})",
    )
    parser.add_argument(
        "-q",
        "--qos",
        type=int,
        default=DEFAULT_QOS,
        choices=[0, 1, 2],
        help=f"QoS level (default: {DEFAULT_QOS})",
    )
    parser.add_argument(
        "-k", "--keepalive", type=int, default=5, help="Keep-alive interval in seconds (default: 5)"
    )

    args = parser.parse_args()

    # Configuration
    config = {
        "url": args.url,
        "pub_topic": args.pub_topic,
        "sub_topic": args.sub_topic,
        "qos": args.qos,
        "keepalive": args.keepalive,
    }

    # Register signal handlers
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    # Create manager
    manager = Manager()

    try:
        # Add timer for reconnection and ping (every 3 seconds)
        manager.timer_add(
            3000,  # 3 seconds
            repeat=True,
            run_now=True,
            callback=lambda: timer_callback(manager, config),
        )

        print("MQTT Client starting...")
        print(f"  URL: {config['url']}")
        print(f"  Subscribe: {config['sub_topic']}")
        print(f"  Publish: {config['pub_topic']}")
        print(f"  QoS: {config['qos']}")
        print(f"  Keep-alive: {config['keepalive']}s")
        print("Press Ctrl+C to exit")

        # Event loop
        while not shutdown_requested:
            manager.poll(100)

        print("\nShutting down...")

        # Graceful disconnect
        if mqtt_conn is not None:
            try:
                mqtt_conn.mqtt_disconnect()
                manager.poll(100)
            except RuntimeError:
                pass

    finally:
        manager.close()
        print("Client stopped cleanly")


if __name__ == "__main__":
    main()
