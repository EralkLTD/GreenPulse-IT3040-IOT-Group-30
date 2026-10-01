import json


class TelemetryValidationError(Exception):
    """Raised when received telemetry is invalid."""


class TelemetryService:
    """Parses and validates telemetry received from GreenPulse devices."""

    REQUIRED_FIELDS = {
        "device_id": str,
        "temperature": (int, float),
        "humidity": (int, float),
        "soil_moisture": (int, float),
        "ph": (int, float),
        "mq135_raw": (int, float),
    }

    @classmethod
    def parse_and_validate(cls, payload: str) -> dict:
        """
        Convert an MQTT JSON payload into a validated Python dictionary.
        """

        # Step 1: Parse JSON
        try:
            data = json.loads(payload)
        except json.JSONDecodeError as error:
            raise TelemetryValidationError(
                f"Invalid JSON: {error.msg}"
            ) from error

        # Step 2: Payload must be a JSON object
        if not isinstance(data, dict):
            raise TelemetryValidationError(
                "Telemetry payload must be a JSON object."
            )

        # Step 3: Check required fields and their data types
        for field, expected_type in cls.REQUIRED_FIELDS.items():

            if field not in data:
                raise TelemetryValidationError(
                    f"Missing required field: {field}"
                )

            if not isinstance(data[field], expected_type):
                raise TelemetryValidationError(
                    f"Invalid type for '{field}'. "
                    f"Received: {type(data[field]).__name__}"
                )

        # Step 4: Basic sensible-range validation
        if not -40 <= data["temperature"] <= 85:
            raise TelemetryValidationError(
                "Temperature is outside the supported range."
            )

        if not 0 <= data["humidity"] <= 100:
            raise TelemetryValidationError(
                "Humidity must be between 0 and 100."
            )

        if not 0 <= data["soil_moisture"] <= 100:
            raise TelemetryValidationError(
                "Soil moisture must be between 0 and 100."
            )

        if not 0 <= data["ph"] <= 14:
            raise TelemetryValidationError(
                "pH must be between 0 and 14."
            )

        if data["mq135_raw"] < 0:
            raise TelemetryValidationError(
                "MQ-135 raw value cannot be negative."
            )

        return data