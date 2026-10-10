import json

from greenpulse.crop_catalog import (
    get_crop,
    get_supported_crops,
    normalize_crop_name,
)


class PlantConfigError(Exception):
    """Raised when a GreenPulse plant configuration is invalid."""
    pass


class PlantService:
    """
    Manages the active GreenPulse plant selection.

    crop_catalog.py is the single source of truth for
    supported plant names and plant profiles.
    """

    def __init__(self):
        self.current_crop_name = None


    def parse_and_set_crop(self, payload: str) -> dict:
        """
        Parse a plant configuration MQTT message.

        Expected payload:
        {
            "plant_type": "Tomato"
        }
        """

        # -------------------------------------------------
        # Parse JSON
        # -------------------------------------------------

        try:
            data = json.loads(payload)

        except json.JSONDecodeError as error:
            raise PlantConfigError(
                f"Invalid configuration JSON: {error.msg}"
            ) from error


        # -------------------------------------------------
        # Validate payload
        # -------------------------------------------------

        if not isinstance(data, dict):
            raise PlantConfigError(
                "Plant configuration must be a JSON object."
            )


        if "plant_type" not in data:
            raise PlantConfigError(
                "Missing required field: plant_type"
            )


        plant_type = data["plant_type"]


        if not isinstance(plant_type, str):
            raise PlantConfigError(
                "plant_type must be a string."
            )


        plant_type = plant_type.strip()


        if not plant_type:
            raise PlantConfigError(
                "plant_type cannot be empty."
            )


        # -------------------------------------------------
        # Normalize against crop_catalog.py
        # -------------------------------------------------

        normalized_name = normalize_crop_name(
            plant_type
        )


        if normalized_name is None:
            raise PlantConfigError(
                f"Unsupported greenhouse crop: {plant_type}"
            )


        # -------------------------------------------------
        # Verify crop exists
        # -------------------------------------------------

        crop = get_crop(
            normalized_name
        )


        if crop is None:
            raise PlantConfigError(
                f"Unsupported greenhouse crop: {plant_type}"
            )


        # -------------------------------------------------
        # Save current selection
        # -------------------------------------------------

        self.current_crop_name = normalized_name


        # IMPORTANT:
        # get_crop() does not contain "name" or "category".
        # The canonical normalized name is therefore used
        # directly as the crop name.
        #
        # Keep category for compatibility with the existing
        # database/MQTT code.

        return {
            "crop_id": crop["crop_id"],
            "name": normalized_name,
            "category": "Greenhouse Crop",
        }


    def get_current_crop(self):
        """
        Return the currently selected crop.
        """

        if self.current_crop_name is None:
            return None


        crop = get_crop(
            self.current_crop_name
        )


        if crop is None:
            return None


        return {
            "crop_id": crop["crop_id"],
            "name": self.current_crop_name,
            "category": "Greenhouse Crop",
        }


    def get_supported_crops(self):
        """
        Return all plants supported by crop_catalog.py.
        """

        result = []


        for crop_name in get_supported_crops():

            crop = get_crop(
                crop_name
            )


            if crop is None:
                continue


            result.append(
                {
                    "crop_id": crop["crop_id"],
                    "name": crop_name,
                    "category": "Greenhouse Crop",
                }
            )


        return result