import json

from greenpulse.crop_catalog import CROP_CATALOG


class PlantConfigError(Exception):
    """Raised when a plant configuration message is invalid."""


class PlantService:
    """Manages greenhouse crop selection for GreenPulse."""

    def __init__(self):
        self.current_crop_id = None

    def parse_and_set_crop(self, payload: str) -> dict:
        """
        Parse a plant configuration JSON payload,
        validate the crop, and set it as the active crop.
        """

        # Parse JSON
        try:
            data = json.loads(payload)

        except json.JSONDecodeError as error:
            raise PlantConfigError(
                f"Invalid configuration JSON: {error.msg}"
            ) from error

        # Payload must be a JSON object
        if not isinstance(data, dict):
            raise PlantConfigError(
                "Plant configuration must be a JSON object."
            )

        # plant_type is required
        if "plant_type" not in data:
            raise PlantConfigError(
                "Missing required field: plant_type"
            )

        plant_type = data["plant_type"]

        if not isinstance(plant_type, str):
            raise PlantConfigError(
                "plant_type must be a string."
            )

        # Normalize user input
        crop_id = (
            plant_type
            .strip()
            .lower()
            .replace(" ", "_")
        )

        # Validate against catalog
        if crop_id not in CROP_CATALOG:
            raise PlantConfigError(
                f"Unsupported greenhouse crop: {plant_type}"
            )

        # Save current selection
        self.current_crop_id = crop_id

        return self.get_current_crop()

    def get_current_crop(self):
        """Return information about the currently selected crop."""

        if self.current_crop_id is None:
            return None

        crop = CROP_CATALOG[self.current_crop_id]

        return {
            "crop_id": self.current_crop_id,
            "name": crop["name"],
            "category": crop["category"],
        }

    def get_supported_crops(self):
        """Return all greenhouse crops supported by GreenPulse."""

        return [
            {
                "crop_id": crop_id,
                "name": crop["name"],
                "category": crop["category"],
            }
            for crop_id, crop in CROP_CATALOG.items()
        ]