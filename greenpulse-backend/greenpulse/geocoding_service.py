"""
GreenPulse - Geocoding Service

Provides worldwide location search and coordinate resolution
using Open-Meteo Geocoding API with provider abstraction.
"""
from abc import ABC, abstractmethod
import logging
from typing import List, Dict, Any, Optional
import requests

logger = logging.getLogger("greenpulse.geocoding")


class GeocodingServiceError(Exception):
    """Raised when geocoding search or validation fails."""


class GeocodingProvider(ABC):
    """Abstract interface for location search providers."""

    @abstractmethod
    def search(
        self,
        query: str,
        count: int = 8,
        language: str = "en"
    ) -> List[Dict[str, Any]]:
        """Search locations matching query string."""
        pass


class OpenMeteoGeocodingProvider(GeocodingProvider):
    """
    Worldwide location search provider using Open-Meteo Geocoding API.
    Public, keyless, and provides city, state/province, and country.
    """

    API_URL = "https://geocoding-api.open-meteo.com/v1/search"
    DEFAULT_TIMEOUT_SECONDS = 8

    def search(
        self,
        query: str,
        count: int = 8,
        language: str = "en"
    ) -> List[Dict[str, Any]]:
        if not query or not query.strip():
            return []

        clean_query = query.strip()
        params = {
            "name": clean_query,
            "count": max(1, min(count, 20)),
            "language": language,
            "format": "json"
        }

        try:
            response = requests.get(
                self.API_URL,
                params=params,
                timeout=self.DEFAULT_TIMEOUT_SECONDS,
                headers={"User-Agent": "GreenPulse-IoT-System/2.0"}
            )
        except requests.exceptions.Timeout as err:
            logger.warning("Geocoding API request timed out for '%s': %s", clean_query, err)
            raise GeocodingServiceError(f"Geocoding service timed out for '{clean_query}'.") from err
        except requests.exceptions.RequestException as err:
            logger.warning("Geocoding API network error for '%s': %s", clean_query, err)
            raise GeocodingServiceError(f"Geocoding network error: {err}") from err

        if response.status_code != 200:
            logger.warning(
                "Geocoding API returned HTTP %s: %s",
                response.status_code,
                response.text[:200]
            )
            raise GeocodingServiceError(
                f"Geocoding API returned HTTP status {response.status_code}."
            )

        try:
            data = response.json()
        except Exception as err:
            logger.warning("Failed to parse geocoding JSON: %s", err)
            raise GeocodingServiceError("Invalid JSON returned by geocoding API.") from err

        raw_results = data.get("results")
        if not raw_results or not isinstance(raw_results, list):
            return []

        normalized = []
        for item in raw_results:
            if not isinstance(item, dict):
                continue

            name = item.get("name", "").strip()
            lat = item.get("latitude")
            lon = item.get("longitude")

            if not name or lat is None or lon is None:
                continue

            try:
                lat_float = round(float(lat), 4)
                lon_float = round(float(lon), 4)
            except (ValueError, TypeError):
                continue

            # Reject Null Island / placeholder coordinates
            if abs(lat_float) < 0.0001 and abs(lon_float) < 0.0001:
                continue

            admin1 = item.get("admin1") or ""
            admin1 = admin1.strip()
            country = item.get("country") or ""
            country = country.strip()
            country_code = item.get("country_code") or ""
            country_code = country_code.strip().upper()

            # Format readable display name: e.g. "Colombo, Western Province, Sri Lanka"
            parts = [name]
            if admin1 and admin1 != name:
                parts.append(admin1)
            if country:
                parts.append(country)
            display_name = ", ".join(parts)

            normalized.append({
                "id": item.get("id"),
                "name": name,
                "latitude": lat_float,
                "longitude": lon_float,
                "admin1": admin1 if admin1 else None,
                "country": country if country else None,
                "country_code": country_code if country_code else None,
                "timezone": item.get("timezone"),
                "display_name": display_name,
            })

        return normalized


class GeocodingService:
    """High-level geocoding service used by GreenPulse backend."""

    def __init__(self, provider: Optional[GeocodingProvider] = None):
        self.provider = provider or OpenMeteoGeocodingProvider()

    def search(self, query: str, count: int = 8) -> List[Dict[str, Any]]:
        """
        Search locations worldwide.
        Requires at least 2 characters.
        """
        if not query or len(query.strip()) < 2:
            return []

        return self.provider.search(query.strip(), count=count)

    @staticmethod
    def validate_coordinates(latitude: float, longitude: float) -> bool:
        """
        Check whether latitude and longitude are valid non-placeholder coordinates.
        """
        try:
            lat = float(latitude)
            lon = float(longitude)
        except (ValueError, TypeError):
            return False

        if not -90.0 <= lat <= 90.0:
            return False
        if not -180.0 <= lon <= 180.0:
            return False

        # Reject Null Island (0, 0)
        if abs(lat) < 0.0001 and abs(lon) < 0.0001:
            return False

        return True
