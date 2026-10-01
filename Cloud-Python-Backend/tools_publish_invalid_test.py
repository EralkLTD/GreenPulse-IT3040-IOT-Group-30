import json
import ssl
import time

import paho.mqtt.client as mqtt

from greenpulse.config import Config


TELEMETRY_TOPIC = "greenpulse/device01/telemetry"

# Deliberately invalid telemetry:
# humidity cannot be greater than 100
INVALID_TELEMETRY = {
    "device_id": "device01",
    "temperature": 29.8,
    "humidity": 150,
    "soil_moisture": 43,
    "ph": 6.4,
    "mq135_raw": 1742
}


def main():
    Config.validate()

    client = mqtt.Client(
        callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
        client_id="greenpulse_invalid_test_publisher"
    )

    client.username_pw_set(
        Config.MQTT_USERNAME,
        Config.MQTT_PASSWORD
    )

    client.tls_set(
        cert_reqs=ssl.CERT_REQUIRED,
        tls_version=ssl.PROTOCOL_TLS_CLIENT
    )

    print("Connecting invalid telemetry test publisher...")

    client.connect(
        Config.MQTT_HOST,
        Config.MQTT_PORT,
        keepalive=60
    )

    client.loop_start()

    # Give the MQTT connection time to establish.
    time.sleep(2)

    payload = json.dumps(INVALID_TELEMETRY)

    print(f"Publishing invalid telemetry to: {TELEMETRY_TOPIC}")

    message_info = client.publish(
        topic=TELEMETRY_TOPIC,
        payload=payload,
        qos=1,
        retain=False
    )

    message_info.wait_for_publish(timeout=10)

    if message_info.is_published():
        print("Invalid test message delivered to HiveMQ.")
        print(f"Payload: {payload}")
    else:
        print("ERROR: HiveMQ did not acknowledge the message.")

    time.sleep(2)

    client.disconnect()
    client.loop_stop()

    print("Invalid telemetry test publisher disconnected.")


if __name__ == "__main__":
    main()