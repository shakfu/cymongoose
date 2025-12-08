MQTT Guide
==========

This guide covers MQTT publish/subscribe messaging using cymongoose.

MQTT Client
-----------

Basic Connection
~~~~~~~~~~~~~~~~

.. code-block:: python

    from cymongoose import Manager, MG_EV_MQTT_OPEN, MG_EV_MQTT_MSG

    def handler(conn, ev, data):
        if ev == MG_EV_MQTT_OPEN:
            # Connected to broker
            print(f"Connected, status={data}")

            # Subscribe to topics
            conn.mqtt_sub("sensors/#", qos=1)

        elif ev == MG_EV_MQTT_MSG:
            # Message received
            print(f"Topic: {data.topic}")
            print(f"Message: {data.text}")

    manager = Manager(handler)
    conn = manager.mqtt_connect(
        'mqtt://broker.hivemq.com:1883',
        client_id='my-client',
        clean_session=True,
        keepalive=60,
    )

    while True:
        manager.poll(100)

Connection Options
~~~~~~~~~~~~~~~~~~

.. code-block:: python

    conn = manager.mqtt_connect(
        url='mqtt://broker.example.com:1883',
        handler=mqtt_handler,
        client_id='cymongoose-client',  # Auto-generated if empty
        username='user',                 # Optional
        password='pass',                 # Optional
        clean_session=True,              # Clean session flag
        keepalive=60,                    # Keep-alive in seconds
    )

Publishing Messages
-------------------

Basic Publish
~~~~~~~~~~~~~

.. code-block:: python

    def handler(conn, ev, data):
        if ev == MG_EV_MQTT_OPEN:
            # Publish after connection
            conn.mqtt_pub("sensors/temperature", "23.5", qos=1)

Quality of Service
~~~~~~~~~~~~~~~~~~

.. code-block:: python

    # QoS 0: At most once (fire and forget)
    conn.mqtt_pub("logs/debug", "Debug message", qos=0)

    # QoS 1: At least once (acknowledged)
    conn.mqtt_pub("sensors/data", "42", qos=1)

    # QoS 2: Exactly once (guaranteed)
    conn.mqtt_pub("critical/alert", "ALERT!", qos=2)

Retain Flag
~~~~~~~~~~~

.. code-block:: python

    # Retained message (broker stores for new subscribers)
    conn.mqtt_pub("status/online", "true", qos=1, retain=True)

Binary Messages
~~~~~~~~~~~~~~~

.. code-block:: python

    # Publish binary data
    binary_data = bytes([0x01, 0x02, 0x03])
    conn.mqtt_pub("data/binary", binary_data, qos=1)

Subscribing to Topics
---------------------

Basic Subscribe
~~~~~~~~~~~~~~~

.. code-block:: python

    def handler(conn, ev, data):
        if ev == MG_EV_MQTT_OPEN:
            # Subscribe to single topic
            conn.mqtt_sub("sensors/temperature", qos=1)

Topic Wildcards
~~~~~~~~~~~~~~~

.. code-block:: python

    # Single-level wildcard (+)
    conn.mqtt_sub("sensors/+/temperature", qos=1)
    # Matches: sensors/room1/temperature, sensors/room2/temperature

    # Multi-level wildcard (#)
    conn.mqtt_sub("sensors/#", qos=1)
    # Matches: sensors/temperature, sensors/room1/temperature, etc.

Multiple Subscriptions
~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: python

    def handler(conn, ev, data):
        if ev == MG_EV_MQTT_OPEN:
            conn.mqtt_sub("sensors/+/temperature", qos=1)
            conn.mqtt_sub("sensors/+/humidity", qos=1)
            conn.mqtt_sub("alerts/#", qos=2)

Receiving Messages
------------------

Message Properties
~~~~~~~~~~~~~~~~~~

.. code-block:: python

    def handler(conn, ev, data):
        if ev == MG_EV_MQTT_MSG:
            # Message properties
            topic = data.topic       # Topic string
            message = data.text      # UTF-8 decoded
            raw_data = data.data     # Raw bytes
            qos = data.qos          # QoS level
            msg_id = data.id        # Message ID

Filtering by Topic
~~~~~~~~~~~~~~~~~~

.. code-block:: python

    def handler(conn, ev, data):
        if ev == MG_EV_MQTT_MSG:
            if data.topic.startswith("sensors/"):
                handle_sensor_data(data)
            elif data.topic.startswith("alerts/"):
                handle_alert(data)

JSON Messages
~~~~~~~~~~~~~

.. code-block:: python

    import json

    def handler(conn, ev, data):
        if ev == MG_EV_MQTT_MSG:
            try:
                payload = json.loads(data.text)
                sensor_id = payload["sensor_id"]
                value = payload["value"]
                process_sensor_reading(sensor_id, value)
            except (json.JSONDecodeError, KeyError):
                print("Invalid JSON message")

Keep-Alive and Ping
-------------------

.. code-block:: python

    def handler(conn, ev, data):
        if ev == MG_EV_MQTT_OPEN:
            # Send periodic pings
            def send_ping():
                conn.mqtt_ping()

            manager.timer_add(30000, send_ping, repeat=True)

Complete Example
----------------

Temperature Monitoring System
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: python

    from cymongoose import Manager, MG_EV_MQTT_OPEN, MG_EV_MQTT_MSG
    import json
    import time
    import random

    def handler(conn, ev, data):
        if ev == MG_EV_MQTT_OPEN:
            print("Connected to MQTT broker")

            # Subscribe to all sensor topics
            conn.mqtt_sub("sensors/+/temperature", qos=1)
            conn.mqtt_sub("sensors/+/humidity", qos=1)

        elif ev == MG_EV_MQTT_MSG:
            # Parse topic
            parts = data.topic.split("/")
            sensor_id = parts[1]
            metric = parts[2]

            # Parse value
            value = float(data.text)

            print(f"[{sensor_id}] {metric}: {value}")

            # Check thresholds
            if metric == "temperature" and value > 30:
                alert = {
                    "sensor": sensor_id,
                    "metric": metric,
                    "value": value,
                    "threshold": 30,
                    "timestamp": time.time(),
                }
                conn.mqtt_pub("alerts/high_temp",
                            json.dumps(alert),
                            qos=2, retain=True)

    def publish_readings(conn):
        """Publish simulated sensor readings."""
        sensors = ["sensor1", "sensor2", "sensor3"]

        for sensor in sensors:
            temp = random.uniform(20, 35)
            humidity = random.uniform(40, 80)

            conn.mqtt_pub(f"sensors/{sensor}/temperature",
                         f"{temp:.1f}", qos=1)
            conn.mqtt_pub(f"sensors/{sensor}/humidity",
                         f"{humidity:.1f}", qos=1)

    manager = Manager(handler)
    conn = manager.mqtt_connect(
        'mqtt://broker.hivemq.com:1883',
        client_id='temp-monitor',
    )

    # Publish readings every 5 seconds
    manager.timer_add(5000, lambda: publish_readings(conn), repeat=True)

    while True:
        manager.poll(100)

MQTT Broker (Server)
--------------------

Simple broker implementation:

.. code-block:: python

    from cymongoose import Manager, MG_EV_MQTT_MSG

    # Track subscriptions
    subscriptions = {}  # {topic: [conn1, conn2, ...]}

    def handler(conn, ev, data):
        if ev == MG_EV_MQTT_MSG:
            topic = data.topic

            # Add to subscriptions
            if topic not in subscriptions:
                subscriptions[topic] = []
            subscriptions[topic].append(conn)

            # Forward to subscribers
            for subscriber in subscriptions.get(topic, []):
                if subscriber != conn:
                    subscriber.mqtt_pub(topic, data.data, qos=data.qos)

    manager = Manager(handler)
    manager.mqtt_listen('mqtt://0.0.0.0:1883')

    while True:
        manager.poll(100)

MQTTS (Secure MQTT)
-------------------

With TLS/SSL:

.. code-block:: python

    from cymongoose import TlsOpts, MG_EV_CONNECT

    ca = open("ca.crt", "rb").read()

    def handler(conn, ev, data):
        if ev == MG_EV_CONNECT:
            # Initialize TLS
            opts = TlsOpts(ca=ca, name="broker.example.com")
            conn.tls_init(opts)

        elif ev == MG_EV_MQTT_OPEN:
            print("Secure connection established")
            conn.mqtt_sub("sensors/#", qos=1)

    manager = Manager(handler)
    manager.mqtt_connect('mqtts://broker.example.com:8883')

Best Practices
--------------

1. **Use QoS 1 or 2** for important messages
2. **Set appropriate keep-alive** (default 60 seconds)
3. **Handle reconnection** with timers
4. **Use topic hierarchy** for organization
5. **Validate JSON** before parsing
6. **Monitor connection status** via ``MG_EV_MQTT_OPEN``
7. **Clean up subscriptions** on disconnect

See Also
--------

- :doc:`tls` - Secure MQTT (MQTTS)
- :doc:`../examples` - Complete MQTT examples
- :doc:`../api/connection` - Connection API
