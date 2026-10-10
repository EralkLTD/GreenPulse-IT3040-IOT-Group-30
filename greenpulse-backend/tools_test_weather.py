import json

from greenpulse.database import Database
from greenpulse.weather_service import (
    WeatherService,
    WeatherServiceError,
)


DEVICE_ID = "device01"


def main():
    print("======================================")
    print("GREENPULSE WEATHER API TEST")
    print("======================================")
    print()

    database = Database()

    location = database.get_latest_device_location(
        DEVICE_ID
    )

    if location is None:
        print("FAILED: No location stored for device01.")
        return

    print("Stored greenhouse location found.")
    print(
        f"Latitude: {location['latitude']}"
    )
    print(
        f"Longitude: {location['longitude']}"
    )

    print()
    print("Requesting weather from Open-Meteo...")

    weather_service = WeatherService()

    try:
        weather = weather_service.get_weather(
            location["latitude"],
            location["longitude"],
        )

    except WeatherServiceError as error:
        print()
        print("WEATHER TEST FAILED")
        print(error)
        return

    print()
    print("Weather received successfully:")
    print(
        json.dumps(
            weather,
            indent=2,
        )
    )

    print()
    print("WEATHER API TEST PASSED")


if __name__ == "__main__":
    main()