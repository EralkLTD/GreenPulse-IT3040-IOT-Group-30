import json
import ssl
import time

import paho.mqtt.client as mqtt

from greenpulse.config import Config


PROFILE_TOPIC = "greenpulse/device01/profile"


def on_connect(
    client,
    userdata,
    flags,
    reason_code,
    properties
):
    if reason_code == 0:

        print("Connected to HiveMQ.")

        client.subscribe(
            PROFILE_TOPIC,
            qos=1
        )

        print(
            f"Subscribed to: {PROFILE_TOPIC}"
        )

    else:

        print(
            f"Connection failed: {reason_code}"
        )


def on_message(
    client,
    userdata,
    message
):
    print("\n======================================")
    print("GREENPULSE PROFILE RECEIVED")
    print("======================================")

    try:

        payload = message.payload.decode(
            "utf-8"
        )

        profile = json.loads(
            payload
        )

        print(
            json.dumps(
                profile,
                indent=2
            )
        )

        print("\nMQTT Information")
        print("--------------------------------------")

        print(
            f"Topic: {message.topic}"
        )

        print(
            f"QoS: {message.qos}"
        )

        print(
            f"Retained: {message.retain}"
        )

        print("\n======================================")
        print("PROFILE SUBSCRIPTION TEST PASSED")
        print("======================================")

    except Exception as error:

        print(
            f"ERROR: {error}"
        )

    # We only need one profile for this test.
    client.disconnect()


def main():

    Config.validate()

    client = mqtt.Client(
        callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
        client_id="greenpulse_profile_test"
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

    print("Connecting profile subscriber...")

    client.connect(
        Config.MQTT_HOST,
        Config.MQTT_PORT,
        keepalive=60
    )

    client.loop_start()

    # Allow enough time to connect and receive
    # the retained profile.
    time.sleep(10)

    client.loop_stop()

    print("\nProfile subscriber finished.")


if __name__ == "__main__":
    main()