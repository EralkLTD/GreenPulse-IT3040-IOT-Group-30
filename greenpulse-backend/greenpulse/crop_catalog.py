"""
GreenPulse - Crop Catalog

Central source of deterministic plant health profiles.

Gemini is NOT used to generate sensor thresholds.
Gemini should only use these profiles together with:
- live ESP32 telemetry
- weather data
- notification/email context

to generate care advice.

Profile fields:
- air_temperature: °C
- humidity: %
- soil_moisture: %
- soil_temperature: °C
- light_preference: BRIGHT / DARK / EITHER
"""

from copy import deepcopy


# ============================================================
# CROP CATALOG
# ============================================================

CROP_CATALOG = {

    # --------------------------------------------------------
    # FRUITING VEGETABLES
    # --------------------------------------------------------

    "Tomato": {
        "crop_id": "tomato",
        "air_temperature": {"min": 18.0, "max": 28.0},
        "humidity": {"min": 50.0, "max": 75.0},
        "soil_moisture": {"min": 60.0, "max": 80.0},
        "soil_temperature": {"min": 18.0, "max": 26.0},
        "light_preference": "BRIGHT",
    },

    "Cherry Tomato": {
        "crop_id": "cherry_tomato",
        "air_temperature": {"min": 18.0, "max": 28.0},
        "humidity": {"min": 50.0, "max": 75.0},
        "soil_moisture": {"min": 60.0, "max": 80.0},
        "soil_temperature": {"min": 18.0, "max": 26.0},
        "light_preference": "BRIGHT",
    },

    "Bell Pepper": {
        "crop_id": "bell_pepper",
        "air_temperature": {"min": 20.0, "max": 30.0},
        "humidity": {"min": 50.0, "max": 75.0},
        "soil_moisture": {"min": 55.0, "max": 75.0},
        "soil_temperature": {"min": 18.0, "max": 27.0},
        "light_preference": "BRIGHT",
    },

    "Chilli Pepper": {
        "crop_id": "chilli_pepper",
        "air_temperature": {"min": 20.0, "max": 30.0},
        "humidity": {"min": 50.0, "max": 70.0},
        "soil_moisture": {"min": 50.0, "max": 70.0},
        "soil_temperature": {"min": 18.0, "max": 28.0},
        "light_preference": "BRIGHT",
    },

    "Cucumber": {
        "crop_id": "cucumber",
        "air_temperature": {"min": 20.0, "max": 30.0},
        "humidity": {"min": 60.0, "max": 85.0},
        "soil_moisture": {"min": 65.0, "max": 85.0},
        "soil_temperature": {"min": 18.0, "max": 28.0},
        "light_preference": "BRIGHT",
    },

    "Eggplant": {
        "crop_id": "eggplant",
        "air_temperature": {"min": 21.0, "max": 30.0},
        "humidity": {"min": 50.0, "max": 75.0},
        "soil_moisture": {"min": 55.0, "max": 75.0},
        "soil_temperature": {"min": 20.0, "max": 28.0},
        "light_preference": "BRIGHT",
    },

    "Zucchini": {
        "crop_id": "zucchini",
        "air_temperature": {"min": 18.0, "max": 28.0},
        "humidity": {"min": 50.0, "max": 75.0},
        "soil_moisture": {"min": 55.0, "max": 80.0},
        "soil_temperature": {"min": 18.0, "max": 26.0},
        "light_preference": "BRIGHT",
    },

    "Okra": {
        "crop_id": "okra",
        "air_temperature": {"min": 22.0, "max": 32.0},
        "humidity": {"min": 50.0, "max": 75.0},
        "soil_moisture": {"min": 50.0, "max": 70.0},
        "soil_temperature": {"min": 20.0, "max": 30.0},
        "light_preference": "BRIGHT",
    },

    # --------------------------------------------------------
    # LEGUMES
    # --------------------------------------------------------

    "Green Bean": {
        "crop_id": "green_bean",
        "air_temperature": {"min": 18.0, "max": 28.0},
        "humidity": {"min": 50.0, "max": 75.0},
        "soil_moisture": {"min": 50.0, "max": 75.0},
        "soil_temperature": {"min": 16.0, "max": 26.0},
        "light_preference": "BRIGHT",
    },

    "Pea": {
        "crop_id": "pea",
        "air_temperature": {"min": 13.0, "max": 24.0},
        "humidity": {"min": 50.0, "max": 75.0},
        "soil_moisture": {"min": 55.0, "max": 75.0},
        "soil_temperature": {"min": 12.0, "max": 22.0},
        "light_preference": "BRIGHT",
    },

    # --------------------------------------------------------
    # FRUITS
    # --------------------------------------------------------

    "Strawberry": {
        "crop_id": "strawberry",
        "air_temperature": {"min": 15.0, "max": 26.0},
        "humidity": {"min": 55.0, "max": 75.0},
        "soil_moisture": {"min": 55.0, "max": 75.0},
        "soil_temperature": {"min": 15.0, "max": 24.0},
        "light_preference": "BRIGHT",
    },

    "Melon": {
        "crop_id": "melon",
        "air_temperature": {"min": 20.0, "max": 30.0},
        "humidity": {"min": 50.0, "max": 70.0},
        "soil_moisture": {"min": 50.0, "max": 75.0},
        "soil_temperature": {"min": 18.0, "max": 28.0},
        "light_preference": "BRIGHT",
    },

    "Watermelon": {
        "crop_id": "watermelon",
        "air_temperature": {"min": 21.0, "max": 32.0},
        "humidity": {"min": 50.0, "max": 70.0},
        "soil_moisture": {"min": 50.0, "max": 75.0},
        "soil_temperature": {"min": 20.0, "max": 30.0},
        "light_preference": "BRIGHT",
    },

    # --------------------------------------------------------
    # LEAFY GREENS
    # --------------------------------------------------------

    "Lettuce": {
        "crop_id": "lettuce",
        "air_temperature": {"min": 12.0, "max": 24.0},
        "humidity": {"min": 50.0, "max": 75.0},
        "soil_moisture": {"min": 60.0, "max": 80.0},
        "soil_temperature": {"min": 12.0, "max": 22.0},
        "light_preference": "BRIGHT",
    },

    "Spinach": {
        "crop_id": "spinach",
        "air_temperature": {"min": 10.0, "max": 24.0},
        "humidity": {"min": 50.0, "max": 75.0},
        "soil_moisture": {"min": 60.0, "max": 80.0},
        "soil_temperature": {"min": 10.0, "max": 22.0},
        "light_preference": "BRIGHT",
    },

    "Kale": {
        "crop_id": "kale",
        "air_temperature": {"min": 10.0, "max": 24.0},
        "humidity": {"min": 50.0, "max": 75.0},
        "soil_moisture": {"min": 55.0, "max": 80.0},
        "soil_temperature": {"min": 10.0, "max": 22.0},
        "light_preference": "BRIGHT",
    },

    "Swiss Chard": {
        "crop_id": "swiss_chard",
        "air_temperature": {"min": 12.0, "max": 26.0},
        "humidity": {"min": 50.0, "max": 75.0},
        "soil_moisture": {"min": 55.0, "max": 80.0},
        "soil_temperature": {"min": 12.0, "max": 24.0},
        "light_preference": "BRIGHT",
    },

    "Arugula": {
        "crop_id": "arugula",
        "air_temperature": {"min": 10.0, "max": 24.0},
        "humidity": {"min": 50.0, "max": 75.0},
        "soil_moisture": {"min": 55.0, "max": 75.0},
        "soil_temperature": {"min": 10.0, "max": 22.0},
        "light_preference": "BRIGHT",
    },

    "Pak Choi": {
        "crop_id": "pak_choi",
        "air_temperature": {"min": 12.0, "max": 25.0},
        "humidity": {"min": 55.0, "max": 80.0},
        "soil_moisture": {"min": 60.0, "max": 80.0},
        "soil_temperature": {"min": 12.0, "max": 23.0},
        "light_preference": "BRIGHT",
    },

    "Cabbage": {
        "crop_id": "cabbage",
        "air_temperature": {"min": 12.0, "max": 24.0},
        "humidity": {"min": 55.0, "max": 80.0},
        "soil_moisture": {"min": 60.0, "max": 80.0},
        "soil_temperature": {"min": 12.0, "max": 22.0},
        "light_preference": "BRIGHT",
    },

    "Celery": {
        "crop_id": "celery",
        "air_temperature": {"min": 15.0, "max": 24.0},
        "humidity": {"min": 55.0, "max": 80.0},
        "soil_moisture": {"min": 65.0, "max": 85.0},
        "soil_temperature": {"min": 14.0, "max": 22.0},
        "light_preference": "BRIGHT",
    },

    # --------------------------------------------------------
    # HERBS
    # --------------------------------------------------------

    "Basil": {
        "crop_id": "basil",
        "air_temperature": {"min": 18.0, "max": 30.0},
        "humidity": {"min": 50.0, "max": 75.0},
        "soil_moisture": {"min": 50.0, "max": 75.0},
        "soil_temperature": {"min": 18.0, "max": 26.0},
        "light_preference": "BRIGHT",
    },

    "Mint": {
        "crop_id": "mint",
        "air_temperature": {"min": 15.0, "max": 28.0},
        "humidity": {"min": 50.0, "max": 80.0},
        "soil_moisture": {"min": 60.0, "max": 85.0},
        "soil_temperature": {"min": 15.0, "max": 25.0},
        "light_preference": "EITHER",
    },

    "Coriander": {
        "crop_id": "coriander",
        "air_temperature": {"min": 12.0, "max": 26.0},
        "humidity": {"min": 50.0, "max": 75.0},
        "soil_moisture": {"min": 55.0, "max": 75.0},
        "soil_temperature": {"min": 12.0, "max": 24.0},
        "light_preference": "BRIGHT",
    },

    "Parsley": {
        "crop_id": "parsley",
        "air_temperature": {"min": 12.0, "max": 26.0},
        "humidity": {"min": 50.0, "max": 75.0},
        "soil_moisture": {"min": 55.0, "max": 80.0},
        "soil_temperature": {"min": 12.0, "max": 24.0},
        "light_preference": "BRIGHT",
    },

    "Dill": {
        "crop_id": "dill",
        "air_temperature": {"min": 12.0, "max": 26.0},
        "humidity": {"min": 45.0, "max": 70.0},
        "soil_moisture": {"min": 50.0, "max": 70.0},
        "soil_temperature": {"min": 12.0, "max": 24.0},
        "light_preference": "BRIGHT",
    },

    "Oregano": {
        "crop_id": "oregano",
        "air_temperature": {"min": 15.0, "max": 28.0},
        "humidity": {"min": 40.0, "max": 70.0},
        "soil_moisture": {"min": 40.0, "max": 65.0},
        "soil_temperature": {"min": 15.0, "max": 25.0},
        "light_preference": "BRIGHT",
    },

    "Thyme": {
        "crop_id": "thyme",
        "air_temperature": {"min": 15.0, "max": 28.0},
        "humidity": {"min": 40.0, "max": 65.0},
        "soil_moisture": {"min": 35.0, "max": 60.0},
        "soil_temperature": {"min": 15.0, "max": 25.0},
        "light_preference": "BRIGHT",
    },

    "Rosemary": {
        "crop_id": "rosemary",
        "air_temperature": {"min": 15.0, "max": 28.0},
        "humidity": {"min": 40.0, "max": 65.0},
        "soil_moisture": {"min": 35.0, "max": 60.0},
        "soil_temperature": {"min": 15.0, "max": 25.0},
        "light_preference": "BRIGHT",
    },

    "Sage": {
        "crop_id": "sage",
        "air_temperature": {"min": 15.0, "max": 28.0},
        "humidity": {"min": 40.0, "max": 65.0},
        "soil_moisture": {"min": 40.0, "max": 65.0},
        "soil_temperature": {"min": 15.0, "max": 25.0},
        "light_preference": "BRIGHT",
    },

    "Chives": {
        "crop_id": "chives",
        "air_temperature": {"min": 12.0, "max": 26.0},
        "humidity": {"min": 50.0, "max": 75.0},
        "soil_moisture": {"min": 55.0, "max": 75.0},
        "soil_temperature": {"min": 12.0, "max": 24.0},
        "light_preference": "BRIGHT",
    },

    # --------------------------------------------------------
    # ROOT VEGETABLES
    # --------------------------------------------------------

    "Radish": {
        "crop_id": "radish",
        "air_temperature": {"min": 10.0, "max": 24.0},
        "humidity": {"min": 50.0, "max": 75.0},
        "soil_moisture": {"min": 55.0, "max": 75.0},
        "soil_temperature": {"min": 10.0, "max": 22.0},
        "light_preference": "BRIGHT",
    },

    "Beetroot": {
        "crop_id": "beetroot",
        "air_temperature": {"min": 10.0, "max": 25.0},
        "humidity": {"min": 50.0, "max": 75.0},
        "soil_moisture": {"min": 55.0, "max": 75.0},
        "soil_temperature": {"min": 10.0, "max": 23.0},
        "light_preference": "BRIGHT",
    },

    "Carrot": {
        "crop_id": "carrot",
        "air_temperature": {"min": 10.0, "max": 24.0},
        "humidity": {"min": 50.0, "max": 75.0},
        "soil_moisture": {"min": 55.0, "max": 75.0},
        "soil_temperature": {"min": 10.0, "max": 22.0},
        "light_preference": "BRIGHT",
    },

    "Spring Onion": {
        "crop_id": "spring_onion",
        "air_temperature": {"min": 12.0, "max": 26.0},
        "humidity": {"min": 50.0, "max": 75.0},
        "soil_moisture": {"min": 55.0, "max": 75.0},
        "soil_temperature": {"min": 12.0, "max": 24.0},
        "light_preference": "BRIGHT",
    },

    # --------------------------------------------------------
    # BRASSICAS
    # --------------------------------------------------------

    "Broccoli": {
        "crop_id": "broccoli",
        "air_temperature": {"min": 12.0, "max": 24.0},
        "humidity": {"min": 55.0, "max": 80.0},
        "soil_moisture": {"min": 60.0, "max": 80.0},
        "soil_temperature": {"min": 12.0, "max": 22.0},
        "light_preference": "BRIGHT",
    },

    "Cauliflower": {
        "crop_id": "cauliflower",
        "air_temperature": {"min": 12.0, "max": 24.0},
        "humidity": {"min": 55.0, "max": 80.0},
        "soil_moisture": {"min": 60.0, "max": 80.0},
        "soil_temperature": {"min": 12.0, "max": 22.0},
        "light_preference": "BRIGHT",
    },
}


# ============================================================
# LOOKUP HELPERS
# ============================================================

def normalize_crop_name(name: str) -> str:
    """
    Normalize user/MQTT crop names to a catalog name.

    Example:
        ' tomato ' -> 'Tomato'
        'CHILLI PEPPER' -> 'Chilli Pepper'
    """

    if not isinstance(name, str):
        return ""

    requested = name.strip().casefold()

    for crop_name in CROP_CATALOG:
        if crop_name.casefold() == requested:
            return crop_name

    return ""


def get_crop(name: str):
    """
    Return the complete internal crop record.

    Includes crop_id.
    Returns None when unsupported.
    """

    normalized = normalize_crop_name(name)

    if not normalized:
        return None

    return deepcopy(CROP_CATALOG[normalized])


def get_profile(name: str):
    """
    Return the MQTT-safe plant profile.

    crop_id is deliberately excluded because the ESP32 and
    Node-RED only need the plant name and operating ranges.
    """

    normalized = normalize_crop_name(name)

    if not normalized:
        return None

    crop = CROP_CATALOG[normalized]

    return {
        "plant": normalized,
        "plant_type": normalized,
        "crop": normalized,

        "air_temperature":
            deepcopy(crop["air_temperature"]),

        "humidity":
            deepcopy(crop["humidity"]),

        "soil_moisture":
            deepcopy(crop["soil_moisture"]),

        "soil_temperature":
            deepcopy(crop["soil_temperature"]),

        "light_preference":
            crop["light_preference"],
    }


def is_supported_crop(name: str) -> bool:
    """Return True when the crop exists in the catalog."""

    return bool(
        normalize_crop_name(name)
    )


def get_supported_crops():
    """Return all supported crop names."""

    return list(
        CROP_CATALOG.keys()
    )


def get_crop_by_id(crop_id: str):
    """
    Find a crop using its internal crop_id.
    """

    if not isinstance(crop_id, str):
        return None

    requested = crop_id.strip().casefold()

    for crop_name, crop in CROP_CATALOG.items():

        if crop["crop_id"].casefold() == requested:

            result = deepcopy(crop)

            result["name"] = crop_name

            return result

    return None