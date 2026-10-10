import json
import ssl
import time

import paho.mqtt.client as mqtt

from greenpulse.config import Config


TELEMETRY_TOPIC = "greenpulse/device01/telemetry"


# =====================================================
# TEST TELEMETRY
# Simulates the current GreenPulse ESP32 hardware
# =====================================================

TEST_TELEMETRY = {
    "device_id": "device01",
    "air_temperature": 29.4,
    "humidity": 73.0,
    "soil_moisture": 42,
    "soil_moisture_raw": 2500,
    "light": "BRIGHT",
    "soil_temperature": 27.2
}


def main():

    # Validate .env configuration
    Config.validate()

    # -------------------------------------------------
    # Create MQTT client
    # -------------------------------------------------

    client = mqtt.Client(
        callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
        client_id="greenpulse_test_publisher"
    )

    # -------------------------------------------------
    # Authentication
    # -------------------------------------------------

    client.username_pw_set(
        Config.MQTT_USERNAME,
        Config.MQTT_PASSWORD
    )

    # -------------------------------------------------
    # TLS
    # -------------------------------------------------

    client.tls_set(
        cert_reqs=ssl.CERT_REQUIRED,
        tls_version=ssl.PROTOCOL_TLS_CLIENT
    )

    print("Connecting test publisher...")

    # -------------------------------------------------
    # Connect to HiveMQ
    # -------------------------------------------------

    client.connect(
        Config.MQTT_HOST,
        Config.MQTT_PORT,
        keepalive=60
    )

    client.loop_start()

    # Give MQTT connection time to establish
    time.sleep(2)

    # -------------------------------------------------
    # Convert telemetry dictionary to JSON
    # -------------------------------------------------

    payload = json.dumps(
        TEST_TELEMETRY
    )

    print(
        f"Publishing to: {TELEMETRY_TOPIC}"
    )

    print(
        f"Payload: {payload}"
    )

    # -------------------------------------------------
    # Publish telemetry
    # -------------------------------------------------

    message_info = client.publish(
        topic=TELEMETRY_TOPIC,
        payload=payload,
        qos=1,
        retain=False
    )

    # Wait for HiveMQ acknowledgement
    message_info.wait_for_publish(
        timeout=10
    )

    if message_info.is_published():

        print(
            "HiveMQ acknowledged the test telemetry."
        )

        print(
            f"Message ID: {message_info.mid}"
        )

    else:

        print(
            "ERROR: HiveMQ did not acknowledge "
            "the test telemetry."
        )

    # Give network loop time to finish
    time.sleep(2)

    # -------------------------------------------------
    # Disconnect
    # -------------------------------------------------

    client.disconnect()

    client.loop_stop()

    print(
        "Test publisher disconnected."
    )


if __name__ == "__main__":
    main()