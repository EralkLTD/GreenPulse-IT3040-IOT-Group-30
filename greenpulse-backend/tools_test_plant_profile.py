from greenpulse.database import Database
from greenpulse.plant_profile_service import (
    PlantProfileService,
    PlantProfileValidationError,
)


DEVICE_ID = "device01"


# =====================================================
# TEST PROFILE
# =====================================================
#
# IMPORTANT:
# These values are only test data used to verify the
# software pipeline. They are NOT final agronomic
# recommendations for Tomato.
#
# Gemini will later generate the actual plant profile.
#
# =====================================================

TEST_PROFILE = {
    "plant": "Tomato",

    "air_temperature": {
        "min": 20.0,
        "max": 30.0
    },

    "humidity": {
        "min": 50.0,
        "max": 75.0
    },

    "soil_moisture": {
        "min": 40.0,
        "max": 70.0
    },

    "soil_temperature": {
        "min": 18.0,
        "max": 28.0
    },

    "light_preference": "BRIGHT"
}


def main():

    print("======================================")
    print("GreenPulse Plant Profile Test")
    print("======================================")

    try:

        # ---------------------------------------------
        # Validate test profile
        # ---------------------------------------------

        print("\n1. Validating plant profile...")

        validated_profile = (
            PlantProfileService.validate_profile(
                TEST_PROFILE
            )
        )

        print("Plant profile validation passed.")

        # ---------------------------------------------
        # Initialize database
        # ---------------------------------------------

        database = Database()

        # ---------------------------------------------
        # Save profile
        # ---------------------------------------------

        print("\n2. Saving plant profile to SQLite...")

        record_id = database.save_plant_profile(
            DEVICE_ID,
            validated_profile
        )

        print(
            f"Plant profile stored. RecordID={record_id}"
        )

        # ---------------------------------------------
        # Retrieve profile
        # ---------------------------------------------

        print("\n3. Reading profile from SQLite...")

        stored_profile = (
            database.get_latest_plant_profile(
                DEVICE_ID
            )
        )

        if stored_profile is None:

            print(
                "ERROR: Plant profile could not be retrieved."
            )

            return

        # ---------------------------------------------
        # Display result
        # ---------------------------------------------

        print("\nStored Plant Profile")
        print("--------------------------------------")

        print(
            f"Plant: {stored_profile['plant']}"
        )

        print(
            "Air Temperature: "
            f"{stored_profile['air_temperature']['min']} "
            "to "
            f"{stored_profile['air_temperature']['max']} C"
        )

        print(
            "Humidity: "
            f"{stored_profile['humidity']['min']} "
            "to "
            f"{stored_profile['humidity']['max']} %"
        )

        print(
            "Soil Moisture: "
            f"{stored_profile['soil_moisture']['min']} "
            "to "
            f"{stored_profile['soil_moisture']['max']} %"
        )

        print(
            "Soil Temperature: "
            f"{stored_profile['soil_temperature']['min']} "
            "to "
            f"{stored_profile['soil_temperature']['max']} C"
        )

        print(
            "Light Preference: "
            f"{stored_profile['light_preference']}"
        )

        print(
            "Created At: "
            f"{stored_profile['created_at']}"
        )

        print("\n======================================")
        print("PLANT PROFILE TEST PASSED")
        print("======================================")

    except PlantProfileValidationError as error:

        print(
            f"PROFILE VALIDATION FAILED: {error}"
        )

    except Exception as error:

        print(
            f"UNEXPECTED ERROR: {error}"
        )


if __name__ == "__main__":
    main()