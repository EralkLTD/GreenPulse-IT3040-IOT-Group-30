import time
from datetime import datetime

import requests


class WeatherServiceError(Exception):
    """Raised when weather information cannot be retrieved."""


class WeatherService:
    """Retrieves weather information from Open-Meteo."""

    API_URL = "https://api.open-meteo.com/v1/forecast"

    # Avoid repeatedly calling the weather API.
    CACHE_SECONDS = 20 * 60

    def __init__(self):
        self._cache = {}

    def get_weather(self, latitude: float, longitude: float) -> dict:
        """
        Get current weather and near-term rain forecast
        for a greenhouse location.
        """

        cache_key = (
            round(float(latitude), 4),
            round(float(longitude), 4),
        )

        cached = self._cache.get(cache_key)

        if cached is not None:
            age = time.time() - cached["cached_at"]

            if age < self.CACHE_SECONDS:
                return cached["data"]

        params = {
            "latitude": latitude,
            "longitude": longitude,

            "current": ",".join([
                "temperature_2m",
                "relative_humidity_2m",
                "precipitation",
                "weather_code",
            ]),

            "hourly": ",".join([
                "precipitation_probability",
                "precipitation",
            ]),

            "forecast_days": 1,
            "timezone": "auto",
        }

        try:
            response = requests.get(
                self.API_URL,
                params=params,
                timeout=10,
            )

            response.raise_for_status()

            raw_data = response.json()

        except requests.RequestException as error:
            raise WeatherServiceError(
                f"Open-Meteo request failed: {error}"
            ) from error

        except ValueError as error:
            raise WeatherServiceError(
                "Open-Meteo returned invalid JSON."
            ) from error

        try:
            current = raw_data["current"]
            hourly = raw_data["hourly"]

            current_time = datetime.fromisoformat(
                current["time"]
            )

            hourly_times = [
                datetime.fromisoformat(value)
                for value in hourly["time"]
            ]

            # Find the nearest/current hourly forecast slot.
            current_index = min(
                range(len(hourly_times)),
                key=lambda index: abs(
                    (
                        hourly_times[index] -
                        current_time
                    ).total_seconds()
                ),
            )

            # Current hour + next five hours.
            end_index = min(
                current_index + 6,
                len(hourly_times),
            )

            rain_probabilities = (
                hourly["precipitation_probability"][
                    current_index:end_index
                ]
            )

            precipitation_values = (
                hourly["precipitation"][
                    current_index:end_index
                ]
            )

            valid_probabilities = [
                value
                for value in rain_probabilities
                if value is not None
            ]

            valid_precipitation = [
                value
                for value in precipitation_values
                if value is not None
            ]

            max_rain_probability = (
                max(valid_probabilities)
                if valid_probabilities
                else 0
            )

            expected_precipitation = round(
                sum(valid_precipitation),
                2,
            )

            weather = {
                "latitude": float(
                    raw_data["latitude"]
                ),

                "longitude": float(
                    raw_data["longitude"]
                ),

                "timezone": raw_data.get(
                    "timezone"
                ),

                "temperature": current[
                    "temperature_2m"
                ],

                "humidity": current[
                    "relative_humidity_2m"
                ],

                "current_precipitation": current[
                    "precipitation"
                ],

                "weather_code": current[
                    "weather_code"
                ],

                "rain_probability_next_6h":
                    max_rain_probability,

                "expected_precipitation_next_6h":
                    expected_precipitation,

                "rain_expected": (
                    max_rain_probability >= 50
                    or expected_precipitation > 0
                ),

                "weather_observed_at": current[
                    "time"
                ],
            }

        except (
            KeyError,
            TypeError,
            ValueError,
            IndexError,
        ) as error:
            raise WeatherServiceError(
                "Unexpected Open-Meteo response format."
            ) from error

        self._cache[cache_key] = {
            "cached_at": time.time(),
            "data": weather,
        }

        return weather