import logging

from greenpulse.database import Database
from greenpulse.email_service import (
    EmailService,
    EmailServiceError,
)
from greenpulse.weather_service import (
    WeatherService,
    WeatherServiceError,
)


logger = logging.getLogger("greenpulse.care")


DEVICE_ID = "device01"


class CareServiceError(Exception):
    """Raised when care context cannot be prepared."""


class CareService:
    """
    Builds the context required for GreenPulse
    AI-generated plant care intelligence.
    """

    def __init__(self):
        self.database = Database()
        self.weather_service = WeatherService()
        self.email_service = EmailService()

    def build_context(
        self,
        telemetry: dict
    ) -> dict:
        """
        Combine:

        - current ESP32 telemetry
        - selected plant
        - validated plant profile
        - greenhouse location
        - Open-Meteo weather
        - relevant Gmail messages
        """

        if not isinstance(telemetry, dict):
            raise CareServiceError(
                "Telemetry must be a dictionary."
            )

        if telemetry.get("device_id") != DEVICE_ID:
            raise CareServiceError(
                "Telemetry belongs to an unexpected device."
            )

        # =================================================
        # SELECTED PLANT
        # =================================================

        plant = (
            self.database.get_latest_plant_configuration(
                DEVICE_ID
            )
        )

        if plant is None:
            raise CareServiceError(
                "No plant configuration is available."
            )

        # =================================================
        # PLANT PROFILE
        # =================================================

        profile = (
            self.database.get_latest_plant_profile(
                DEVICE_ID
            )
        )

        if profile is None:
            raise CareServiceError(
                "No validated plant profile is available."
            )

        # Make sure the stored profile belongs to
        # the currently selected plant.

        selected_plant_name = (
            plant.get("name")
            or plant.get("crop_name")
        )

        if profile["plant"] != selected_plant_name:
            raise CareServiceError(
                "Stored plant profile does not match "
                "the currently selected plant."
            )

        # =================================================
        # LOCATION
        # =================================================

        location = (
            self.database.get_latest_device_location(
                DEVICE_ID
            )
        )

        # =================================================
        # WEATHER
        # =================================================

        weather = None

        if location is not None:
            try:
                weather = (
                    self.weather_service.get_weather(
                        location["latitude"],
                        location["longitude"],
                    )
                )

            except WeatherServiceError as error:
                logger.warning(
                    "Weather unavailable. Reason=%s",
                    error
                )

        # =================================================
        # GMAIL
        # =================================================

        email_messages = []

        try:
            email_messages = (
                self.email_service
                .get_relevant_recent_emails(
                    max_messages=5
                )
            )

        except EmailServiceError as error:
            # Email is optional context.
            # GreenPulse must continue if Gmail fails.

            logger.warning(
                "Gmail context unavailable. Reason=%s",
                error
            )

        # =================================================
        # BUILD AI CONTEXT
        # =================================================

        return {
            "device_id": DEVICE_ID,

            "plant": selected_plant_name,

            "telemetry": {
                "air_temperature":
                    telemetry.get(
                        "air_temperature"
                    ),

                "humidity":
                    telemetry.get(
                        "humidity"
                    ),

                "soil_moisture":
                    telemetry.get(
                        "soil_moisture"
                    ),

                "light":
                    telemetry.get(
                        "light"
                    ),

                "soil_temperature":
                    telemetry.get(
                        "soil_temperature"
                    ),
            },

            "plant_profile": {
                "air_temperature":
                    profile["air_temperature"],

                "humidity":
                    profile["humidity"],

                "soil_moisture":
                    profile["soil_moisture"],

                "soil_temperature":
                    profile["soil_temperature"],

                "light_preference":
                    profile["light_preference"],
            },

            "location": (
                {
                    "latitude": location["latitude"],
                    "longitude": location["longitude"],
                    "location_name": location.get("location_name"),
                    "admin1": location.get("admin1"),
                    "country": location.get("country"),
                    "country_code": location.get("country_code"),
                }
                if location is not None
                else None
            ),

            "weather": weather,

            "relevant_emails": email_messages,
        }