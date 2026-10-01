import os

from dotenv import load_dotenv


# Load environment variables from the local .env file
load_dotenv()


class Config:
    """Application configuration loaded from environment variables."""

    MQTT_HOST = os.getenv("HIVEMQ_HOST")
    MQTT_PORT = int(
        os.getenv("HIVEMQ_PORT", "8883")
    )
    MQTT_USERNAME = os.getenv("HIVEMQ_USERNAME")
    MQTT_PASSWORD = os.getenv("HIVEMQ_PASSWORD")

    @classmethod
    def validate(cls):
        """Check that required MQTT settings exist."""

        required_settings = {
            "HIVEMQ_HOST": cls.MQTT_HOST,
            "HIVEMQ_USERNAME": cls.MQTT_USERNAME,
            "HIVEMQ_PASSWORD": cls.MQTT_PASSWORD,
        }

        missing = [
            name
            for name, value in required_settings.items()
            if not value
        ]

        if missing:
            raise ValueError(
                "Missing required environment variables: "
                + ", ".join(missing)
            )