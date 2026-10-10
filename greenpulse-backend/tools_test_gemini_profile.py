import json

from greenpulse.database import Database
from greenpulse.gemini_service import GeminiService


DEVICE_ID = "device01"
TEST_PLANT = "Tomato"


def main():
    print("======================================")
    print("GreenPulse Gemini Profile Test")
    print("======================================")

    try:
        # ==============================================
        # 1. GENERATE PROFILE
        # ==============================================

        print(
            f"\n1. Requesting Gemini profile for "
            f"{TEST_PLANT}..."
        )

        gemini = GeminiService()

        profile = gemini.generate_plant_profile(
            TEST_PLANT
        )

        # ==============================================
        # 2. DISPLAY VALIDATED PROFILE
        # ==============================================

        print("\n2. Gemini profile generated and validated.")

        print("\nGenerated Profile")
        print("--------------------------------------")

        print(
            json.dumps(
                profile,
                indent=2
            )
        )

        # ==============================================
        # 3. SAVE TO SQLITE
        # ==============================================

        print(
            "\n3. Saving validated profile to SQLite..."
        )

        database = Database()

        record_id = database.save_plant_profile(
            DEVICE_ID,
            profile
        )

        print(
            f"Profile stored successfully. "
            f"RecordID={record_id}"
        )

        # ==============================================
        # 4. READ BACK FROM SQLITE
        # ==============================================

        print(
            "\n4. Reading profile back from SQLite..."
        )

        stored_profile = (
            database.get_latest_plant_profile(
                DEVICE_ID
            )
        )

        if stored_profile is None:
            raise RuntimeError(
                "Profile was saved but could not "
                "be retrieved."
            )

        print("\nStored Profile")
        print("--------------------------------------")

        print(
            json.dumps(
                stored_profile,
                indent=2
            )
        )

        # ==============================================
        # SUCCESS
        # ==============================================

        print("\n======================================")
        print("GEMINI PROFILE TEST PASSED")
        print("======================================")

    except Exception as error:

        print("\n======================================")
        print("GEMINI PROFILE TEST FAILED")
        print("======================================")

        print(
            f"{type(error).__name__}: {error}"
        )


if __name__ == "__main__":
    main()