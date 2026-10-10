"""
GreenPulse - Location Service

Validates greenhouse location payloads from Node-RED or other MQTT clients.
Supports both legacy coordinate-only payloads and new worldwide autocomplete payloads.
Rejects placeholder (0, 0) coordinates and invalid ranges.
"""
import json
from typing import Dict, Any, Optional


class LocationValidationError(Exception):
    """Raised when a GreenPulse location payload is invalid."""


class LocationService:
    """Validates and parses greenhouse location messages."""

    @staticmethod
    def parse_and_validate(payload: str) -> Dict[str, Any]:
        """
        Parse and validate location JSON payload.

        Required fields:
        - device_id: non-empty string
        - latitude: float between -90 and 90, not 0.0
        - longitude: float between -180 and 180, not 0.0

        Optional extended fields:
        - location_name: string (city / town name)
        - admin1: string (province / state / region)
        - country: string
        - country_code: string (ISO 2-letter)
        - geocoding_id: int or str (Open-Meteo ID)
        """
        try:
            data = json.loads(payload)
        except (json.JSONDecodeError, TypeError) as error:
            raise LocationValidationError(
                "Location payload is not valid JSON."
            ) from error

        if not isinstance(data, dict):
            raise LocationValidationError(
                "Location payload must be a JSON object."
            )

        device_id = data.get("device_id")
        latitude = data.get("latitude")
        longitude = data.get("longitude")

        if not isinstance(device_id, str) or not device_id.strip():
            raise LocationValidationError(
                "device_id must be a non-empty string."
            )

        if isinstance(latitude, bool) or not isinstance(latitude, (int, float)):
            raise LocationValidationError(
                "latitude must be numeric."
            )

        if isinstance(longitude, bool) or not isinstance(longitude, (int, float)):
            raise LocationValidationError(
                "longitude must be numeric."
            )

        try:
            lat = round(float(latitude), 6)
            lon = round(float(longitude), 6)
        except (ValueError, TypeError) as error:
            raise LocationValidationError(
                "latitude and longitude could not be converted to float."
            ) from error

        if not -90.0 <= lat <= 90.0:
            raise LocationValidationError(
                "latitude must be between -90 and 90."
            )

        if not -180.0 <= lon <= 180.0:
            raise LocationValidationError(
                "longitude must be between -180 and 180."
            )

        # Reject Null Island / placeholder (0, 0)
        if abs(lat) < 0.0001 and abs(lon) < 0.0001:
            raise LocationValidationError(
                "Placeholder coordinates (0, 0) are not permitted as a real greenhouse location."
            )

        # Parse optional extended fields
        def _clean_str(val: Any) -> Optional[str]:
            if val is None:
                return None
            s = str(val).strip()
            return s if s else None

        location_name = _clean_str(data.get("location_name"))
        admin1 = _clean_str(data.get("admin1"))
        country = _clean_str(data.get("country"))
        country_code = _clean_str(data.get("country_code"))
        if country_code:
            country_code = country_code.upper()

        geocoding_id = data.get("geocoding_id")
        if geocoding_id is not None:
            try:
                geocoding_id = int(geocoding_id)
            except (ValueError, TypeError):
                geocoding_id = None

        return {
            "device_id": device_id.strip(),
            "latitude": lat,
            "longitude": lon,
            "location_name": location_name,
            "admin1": admin1,
            "country": country,
            "country_code": country_code,
            "geocoding_id": geocoding_id,
        }

    @staticmethod
    def format_display_name(location: Optional[Dict[str, Any]]) -> str:
        """Format a human-readable display string for a location."""
        if not location:
            return "Unknown Location"

        name = location.get("location_name")
        country = location.get("country")
        admin1 = location.get("admin1")

        if name and country:
            if admin1 and admin1 != name:
                return f"{name}, {admin1}, {country}"
            return f"{name}, {country}"
        elif name:
            return name
        else:
            lat = location.get("latitude")
            lon = location.get("longitude")
            if lat is not None and lon is not None:
                lat_card = "N" if lat >= 0 else "S"
                lon_card = "E" if lon >= 0 else "W"
                return f"{abs(lat):.4f}° {lat_card}, {abs(lon):.4f}° {lon_card}"
            return "Unknown Location"