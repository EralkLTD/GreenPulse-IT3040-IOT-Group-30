import json

from greenpulse.care_service import CareService


def main():
    print("======================================")
    print("GREENPULSE CARE CONTEXT TEST")
    print("======================================")
    print()

    # Simulated ESP32 telemetry.
    # Everything else comes from the real backend:
    # - selected plant from SQLite
    # - plant profile from SQLite
    # - location from SQLite
    # - weather from Open-Meteo
    # - relevant emails from Gmail

    telemetry = {
        "device_id": "device01",
        "air_temperature": 29.4,
        "humidity": 73.0,
        "soil_moisture": 42,
        "soil_moisture_raw": 2500,
        "light": "BRIGHT",
        "soil_temperature": 27.2,
    }

    print("Building care context...")
    print()

    service = CareService()

    try:
        context = service.build_context(
            telemetry
        )

    except Exception as error:
        print("CARE CONTEXT TEST FAILED")
        print()
        print(error)
        return

    print("Care context built successfully:")
    print()

    print(
        json.dumps(
            context,
            indent=2,
            ensure_ascii=False
        )
    )

    print()
    print("CARE CONTEXT TEST PASSED")


if __name__ == "__main__":
    main()