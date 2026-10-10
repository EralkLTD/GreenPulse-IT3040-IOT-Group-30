import json

from greenpulse.gemini_service import GeminiService


def main():
    print("======================================")
    print("GREENPULSE GEMINI CARE TEST")
    print("======================================")
    print()

    # Controlled test context.
    # We'll connect real telemetry/weather/email after
    # confirming structured care generation works.

    context = {
        "plant": "Tomato",

        "telemetry": {
            "air_temperature": 29.4,
            "humidity": 73.0,
            "soil_moisture": 42,
            "light": "BRIGHT",
            "soil_temperature": 27.2,
        },

        "plant_profile": {
            "air_temperature": {
                "min": 18.0,
                "max": 28.0,
            },

            "humidity": {
                "min": 50.0,
                "max": 75.0,
            },

            "soil_moisture": {
                "min": 60.0,
                "max": 80.0,
            },

            "soil_temperature": {
                "min": 18.0,
                "max": 26.0,
            },

            "light_preference": "BRIGHT",
        },

        "weather": {
            "temperature": 26.4,
            "humidity": 94,
            "current_precipitation": 0.0,
            "weather_code": 3,
            "rain_probability_next_6h": 47,
            "expected_precipitation_next_6h": 0.0,
            "rain_expected": False,
        },

        "relevant_emails": [],
    }

    print("Sending care context to Gemini...")
    print()

    service = GeminiService()

    try:
        result = service.generate_care_response(
            context
        )

    except Exception as error:
        print("GEMINI CARE TEST FAILED")
        print(error)
        return

    print("Gemini care response:")
    print()

    print(
        json.dumps(
            result,
            indent=2,
            ensure_ascii=False
        )
    )

    print()
    print("GEMINI CARE TEST PASSED")


if __name__ == "__main__":
    main()