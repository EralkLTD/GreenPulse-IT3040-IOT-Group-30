import json


class TelemetryValidationError(Exception):
    """Raised when received telemetry is invalid."""


class TelemetryService:
    """Parses and validates GreenPulse sensor telemetry."""

    REQUIRED_FIELDS = {
        "device_id": str,
        "air_temperature": (int, float),
        "humidity": (int, float),
        "soil_moisture": (int, float),
        "soil_moisture_raw": int,
        "light": str,
        "soil_temperature": (int, float),
    }

    @classmethod
    def parse_and_validate(cls, payload: str) -> dict:
        """Parse a JSON payload and validate telemetry values."""

        # -------------------------------------------------
        # Parse JSON
        # -------------------------------------------------

        try:
            data = json.loads(payload)

        except json.JSONDecodeError as error:
            raise TelemetryValidationError(
                f"Invalid JSON: {error.msg}"
            ) from error

        if not isinstance(data, dict):
            raise TelemetryValidationError(
                "Telemetry payload must be a JSON object."
            )

        # -------------------------------------------------
        # Required fields and data types
        # -------------------------------------------------

        for field, expected_type in cls.REQUIRED_FIELDS.items():

            if field not in data:
                raise TelemetryValidationError(
                    f"Missing required field: {field}"
                )

            value = data[field]

            # bool is a subclass of int in Python.
            # Explicitly reject True/False for numeric fields.
            if isinstance(value, bool):
                raise TelemetryValidationError(
                    f"Invalid type for '{field}'. "
                    "Boolean values are not allowed."
                )

            if not isinstance(value, expected_type):
                raise TelemetryValidationError(
                    f"Invalid type for '{field}'. "
                    f"Received: {type(value).__name__}"
                )

        # -------------------------------------------------
        # Device ID
        # -------------------------------------------------

        if not data["device_id"].strip():
            raise TelemetryValidationError(
                "device_id cannot be empty."
            )

        # -------------------------------------------------
        # Air temperature - DHT11
        # -------------------------------------------------

        if not -40 <= data["air_temperature"] <= 85:
            raise TelemetryValidationError(
                "Air temperature is outside the supported range."
            )

        # -------------------------------------------------
        # Humidity - DHT11
        # -------------------------------------------------

        if not 0 <= data["humidity"] <= 100:
            raise TelemetryValidationError(
                "Humidity must be between 0 and 100."
            )

        # -------------------------------------------------
        # Soil moisture percentage
        # -------------------------------------------------

        if not 0 <= data["soil_moisture"] <= 100:
            raise TelemetryValidationError(
                "Soil moisture must be between 0 and 100."
            )

        # -------------------------------------------------
        # Soil moisture raw ADC
        # ESP32 uses 12-bit ADC: 0-4095
        # -------------------------------------------------

        if not 0 <= data["soil_moisture_raw"] <= 4095:
            raise TelemetryValidationError(
                "Soil moisture raw value must be "
                "between 0 and 4095."
            )

        # -------------------------------------------------
        # LDR
        # -------------------------------------------------

        light = data["light"].strip().upper()

        if light not in {"BRIGHT", "DARK"}:
            raise TelemetryValidationError(
                "Light must be either BRIGHT or DARK."
            )

        # Store a standardized value
        data["light"] = light

        # -------------------------------------------------
        # Soil temperature - DS18B20
        # -------------------------------------------------

        if not -55 <= data["soil_temperature"] <= 125:
            raise TelemetryValidationError(
                "Soil temperature is outside the "
                "supported DS18B20 range."
            )

        return data