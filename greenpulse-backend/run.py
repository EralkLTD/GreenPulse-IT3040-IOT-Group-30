from greenpulse.logging_setup import setup_logging
from greenpulse.mqtt_service import MQTTService


def main():
    logger = setup_logging()

    logger.info(
        "Starting GreenPulse backend."
    )

    mqtt_service = MQTTService()

    try:
        mqtt_service.connect()

    except KeyboardInterrupt:
        logger.info(
            "GreenPulse backend stopped by user."
        )

    except Exception:
        logger.exception(
            "GreenPulse backend terminated due to an unexpected error."
        )


if __name__ == "__main__":
    main()