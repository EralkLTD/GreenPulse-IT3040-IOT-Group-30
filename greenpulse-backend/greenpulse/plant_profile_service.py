"""
GreenPulse - Plant Profile Service

This module validates plant profiles before they are:
- stored in the database
- published through MQTT
- used by Node-RED
- synchronized with the ESP32

Plant threshold values now come from the local crop catalog.
Gemini is NOT responsible for generating these thresholds.
"""


class PlantProfileValidationError(Exception):
    """
    Raised when a GreenPulse plant profile contains
    invalid or unsupported values.
    """

    pass


class PlantProfileService:
    """
    Validation service for GreenPulse plant profiles.

    The actual crop thresholds are defined in:

        greenpulse/crop_catalog.py

    This service acts as a safety layer before those
    profiles are used elsewhere in the GreenPulse system.
    """

    # -----------------------------------------------------
    # Required numeric profile ranges
    # -----------------------------------------------------

    REQUIRED_RANGES = (
        "air_temperature",
        "humidity",
        "soil_moisture",
        "soil_temperature",
    )

    # -----------------------------------------------------
    # Supported LDR/light classifications
    # -----------------------------------------------------

    VALID_LIGHT_VALUES = {
        "BRIGHT",
        "DARK",
        "EITHER",
    }

    # =====================================================
    # PUBLIC VALIDATION METHOD
    # =====================================================

    @classmethod
    def validate_profile(cls, profile: dict) -> dict:
        """
        Validate and normalize a GreenPulse plant profile.

        Expected structure:

        {
            "plant": "Tomato",

            "air_temperature": {
                "min": 18.0,
                "max": 28.0
            },

            "humidity": {
                "min": 50.0,
                "max": 75.0
            },

            "soil_moisture": {
                "min": 60.0,
                "max": 80.0
            },

            "soil_temperature": {
                "min": 18.0,
                "max": 26.0
            },

            "light_preference": "BRIGHT"
        }

        Returns:
            dict:
                Validated and normalized profile.

        Raises:
            PlantProfileValidationError:
                If the profile contains invalid data.
        """

        # -------------------------------------------------
        # Validate root object
        # -------------------------------------------------

        if not isinstance(profile, dict):
            raise PlantProfileValidationError(
                "Plant profile must be an object."
            )

        # -------------------------------------------------
        # Validate plant name
        # -------------------------------------------------

        plant = profile.get("plant")

        if not isinstance(plant, str):
            raise PlantProfileValidationError(
                "Plant profile requires a valid plant name."
            )

        plant = plant.strip()

        if not plant:
            raise PlantProfileValidationError(
                "Plant profile requires a valid plant name."
            )

        profile["plant"] = plant

        # -------------------------------------------------
        # Validate required numeric ranges
        # -------------------------------------------------

        for field in cls.REQUIRED_RANGES:

            if field not in profile:
                raise PlantProfileValidationError(
                    f"Missing plant profile field: {field}"
                )

            value_range = profile[field]

            cls._validate_range_structure(
                value_range=value_range,
                field_name=field,
            )

        # -------------------------------------------------
        # Validate system boundaries
        #
        # IMPORTANT:
        # These values are NOT crop recommendations.
        #
        # They are only broad safety boundaries that prevent
        # obviously invalid values from entering GreenPulse.
        # -------------------------------------------------

        cls._validate_range_limits(
            value_range=profile["air_temperature"],
            allowed_min=-40,
            allowed_max=85,
            field_name="air_temperature",
        )

        cls._validate_range_limits(
            value_range=profile["humidity"],
            allowed_min=0,
            allowed_max=100,
            field_name="humidity",
        )

        cls._validate_range_limits(
            value_range=profile["soil_moisture"],
            allowed_min=0,
            allowed_max=100,
            field_name="soil_moisture",
        )

        cls._validate_range_limits(
            value_range=profile["soil_temperature"],
            allowed_min=-55,
            allowed_max=125,
            field_name="soil_temperature",
        )

        # -------------------------------------------------
        # Validate light preference
        # -------------------------------------------------

        light = profile.get("light_preference")

        if not isinstance(light, str):
            raise PlantProfileValidationError(
                "light_preference must be a string."
            )

        light = light.strip().upper()

        if light not in cls.VALID_LIGHT_VALUES:
            raise PlantProfileValidationError(
                "light_preference must be "
                "BRIGHT, DARK, or EITHER."
            )

        profile["light_preference"] = light

        # -------------------------------------------------
        # Return validated profile
        # -------------------------------------------------

        return profile

    # =====================================================
    # RANGE STRUCTURE VALIDATION
    # =====================================================

    @staticmethod
    def _validate_range_structure(
        value_range: dict,
        field_name: str,
    ):
        """
        Validate the basic structure of a min/max range.

        Example:

            {
                "min": 18.0,
                "max": 28.0
            }
        """

        if not isinstance(value_range, dict):
            raise PlantProfileValidationError(
                f"{field_name} must contain min and max values."
            )

        # -------------------------------------------------
        # Check required keys
        # -------------------------------------------------

        if "min" not in value_range:
            raise PlantProfileValidationError(
                f"{field_name} requires a min value."
            )

        if "max" not in value_range:
            raise PlantProfileValidationError(
                f"{field_name} requires a max value."
            )

        minimum = value_range["min"]
        maximum = value_range["max"]

        # -------------------------------------------------
        # Boolean values should NOT count as numbers.
        #
        # In Python:
        # isinstance(True, int) == True
        #
        # Therefore explicitly reject bool.
        # -------------------------------------------------

        if isinstance(minimum, bool):
            raise PlantProfileValidationError(
                f"{field_name} minimum must be numeric."
            )

        if isinstance(maximum, bool):
            raise PlantProfileValidationError(
                f"{field_name} maximum must be numeric."
            )

        # -------------------------------------------------
        # Check numeric types
        # -------------------------------------------------

        if not isinstance(minimum, (int, float)):
            raise PlantProfileValidationError(
                f"{field_name} minimum must be numeric."
            )

        if not isinstance(maximum, (int, float)):
            raise PlantProfileValidationError(
                f"{field_name} maximum must be numeric."
            )

        # -------------------------------------------------
        # Minimum must be below maximum
        # -------------------------------------------------

        if minimum >= maximum:
            raise PlantProfileValidationError(
                f"{field_name} minimum must be lower "
                f"than maximum."
            )

    # =====================================================
    # RANGE BOUNDARY VALIDATION
    # =====================================================

    @staticmethod
    def _validate_range_limits(
        value_range: dict,
        allowed_min: float,
        allowed_max: float,
        field_name: str,
    ):
        """
        Ensure a plant profile remains inside GreenPulse's
        supported system limits.

        These limits protect the system from malformed
        configuration values. They are not crop-specific
        growing recommendations.
        """

        minimum = value_range["min"]
        maximum = value_range["max"]

        if minimum < allowed_min:
            raise PlantProfileValidationError(
                f"{field_name} minimum ({minimum}) "
                f"is below the supported system limit "
                f"({allowed_min})."
            )

        if maximum > allowed_max:
            raise PlantProfileValidationError(
                f"{field_name} maximum ({maximum}) "
                f"is above the supported system limit "
                f"({allowed_max})."
            )