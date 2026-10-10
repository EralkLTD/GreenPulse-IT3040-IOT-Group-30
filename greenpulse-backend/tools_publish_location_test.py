import json
import ssl
import threading

import paho.mqtt.client as mqtt

from greenpulse.config import Config


DEVICE_ID = "device01"
LOCATION_TOPIC = "greenpulse/device01/location"

# TEST coordinates only.
# OpenStreetMap will provide the real selected coordinates later.
TEST_LATITUDE = 6.9271
TEST_LONGITUDE = 79.8612

publish_finished = threading.Event()


def on_connect(
    client,
    userdata,
    flags,
    reason_code,
    properties
):
    if reason_code != 0:
        print(f"Connection failed: {reason_code}")
        publish_finished.set()
        return

    print("Connected to HiveMQ.")

    payload = {
        "device_id": DEVICE_ID,
        "latitude": TEST_LATITUDE,
        "longitude": TEST_LONGITUDE
    }

    print(f"Publishing to: {LOCATION_TOPIC}")
    print("Payload:")
    print(json.dumps(payload, indent=2))

    info = client.publish(
        LOCATION_TOPIC,
        json.dumps(payload),
        qos=1,
        retain=False
    )

    print(f"Message ID: {info.mid}")


def on_publish(
    client,
    userdata,
    mid,
    reason_code,
    properties
):
    print("HiveMQ acknowledged the location message.")
    print(f"Message ID: {mid}")

    publish_finished.set()

    client.disconnect()


def main():
    Config.validate()

    client = mqtt.Client(
        callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
        client_id="greenpulse_location_test"
    )

    client.username_pw_set(
        Config.MQTT_USERNAME,
        Config.MQTT_PASSWORD
    )

    client.tls_set(
        cert_reqs=ssl.CERT_REQUIRED,
        tls_version=ssl.PROTOCOL_TLS_CLIENT
    )

    client.on_connect = on_connect
    client.on_publish = on_publish

    print("======================================")
    print("GREENPULSE LOCATION MQTT TEST")
    print("======================================")
    print()

    print("Connecting location test publisher...")

    client.connect(
        Config.MQTT_HOST,
        Config.MQTT_PORT,
        keepalive=60
    )

    client.loop_start()

    if not publish_finished.wait(timeout=15):
        print(
            "Timed out waiting for MQTT "
            "publish acknowledgement."
        )

    client.loop_stop()

    print()
    print("Location test publisher finished.")


if __name__ == "__main__":
    main()