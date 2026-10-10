import json
import ssl
import time

import paho.mqtt.client as mqtt

from greenpulse.config import Config


CONFIG_TOPIC = "greenpulse/device01/config"

TEST_CONFIG = {
    "plant_type": "Tomato"
}


def main():
    Config.validate()

    client = mqtt.Client(
        callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
        client_id="greenpulse_config_test_publisher"
    )

    client.username_pw_set(
        Config.MQTT_USERNAME,
        Config.MQTT_PASSWORD
    )

    client.tls_set(
        cert_reqs=ssl.CERT_REQUIRED,
        tls_version=ssl.PROTOCOL_TLS_CLIENT
    )

    print("Connecting config test publisher...")

    client.connect(
        Config.MQTT_HOST,
        Config.MQTT_PORT,
        keepalive=60
    )

    client.loop_start()

    # Allow the MQTT connection to establish.
    time.sleep(2)

    payload = json.dumps(TEST_CONFIG)

    print(f"Publishing to: {CONFIG_TOPIC}")
    print(f"Payload: {payload}")

    message_info = client.publish(
        topic=CONFIG_TOPIC,
        payload=payload,
        qos=1,
        retain=False
    )

    # Wait until HiveMQ acknowledges the QoS 1 message.
    message_info.wait_for_publish(timeout=10)

    if message_info.is_published():
        print("HiveMQ acknowledged the plant configuration.")
        print(f"Message ID: {message_info.mid}")
    else:
        print(
            "ERROR: HiveMQ did not acknowledge "
            "the plant configuration."
        )

    time.sleep(2)

    client.disconnect()
    client.loop_stop()

    print("Config test publisher disconnected.")


if __name__ == "__main__":
    main()