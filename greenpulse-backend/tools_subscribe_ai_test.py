import json
import ssl
import time

import paho.mqtt.client as mqtt

from greenpulse.config import Config


AI_TOPIC = "greenpulse/device01/ai"


def on_connect(
    client,
    userdata,
    flags,
    reason_code,
    properties
):
    if reason_code != 0:
        print(
            f"MQTT connection failed: {reason_code}"
        )
        return

    print("Connected to HiveMQ.")
    print(f"Subscribing to: {AI_TOPIC}")

    client.subscribe(
        AI_TOPIC,
        qos=1
    )


def on_message(
    client,
    userdata,
    message
):
    print("\nAI message received!")
    print(f"Topic: {message.topic}")
    print(f"QoS: {message.qos}")
    print(f"Retained: {message.retain}")

    try:
        payload = json.loads(
            message.payload.decode("utf-8")
        )

        print("\nPayload:")
        print(
            json.dumps(
                payload,
                indent=2,
                ensure_ascii=False
            )
        )

    except Exception as error:
        print(
            f"Could not decode AI payload: {error}"
        )

    client.disconnect()


def main():
    Config.validate()

    client = mqtt.Client(
        callback_api_version=(
            mqtt.CallbackAPIVersion.VERSION2
        ),
        client_id=(
            f"greenpulse_ai_test_{int(time.time())}"
        )
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
    client.on_message = on_message

    print("======================================")
    print("GreenPulse AI MQTT Subscriber Test")
    print("======================================")
    print()
    print("Connecting to HiveMQ...")

    client.connect(
        Config.MQTT_HOST,
        Config.MQTT_PORT,
        keepalive=60
    )

    client.loop_forever()


if __name__ == "__main__":
    main()