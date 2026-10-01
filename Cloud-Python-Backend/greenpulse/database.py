import sqlite3
from datetime import datetime, timezone
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent.parent
DATABASE_DIR = BASE_DIR / "data"
DATABASE_PATH = DATABASE_DIR / "greenpulse.db"


class Database:
    """Handles SQLite storage for the GreenPulse backend."""

    def __init__(self):
        DATABASE_DIR.mkdir(parents=True, exist_ok=True)
        self._create_tables()

    def _get_connection(self):
        """Create and return a SQLite connection."""

        return sqlite3.connect(DATABASE_PATH)

    def _create_tables(self):
        """Create GreenPulse database tables if they do not exist."""

        with self._get_connection() as connection:
            cursor = connection.cursor()

            # Sensor telemetry
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS telemetry (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    device_id TEXT NOT NULL,
                    temperature REAL NOT NULL,
                    humidity REAL NOT NULL,
                    soil_moisture REAL NOT NULL,
                    ph REAL NOT NULL,
                    mq135_raw REAL NOT NULL,
                    received_at TEXT NOT NULL
                )
                """
            )

            # Plant/crop configuration history
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS plant_configuration (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    device_id TEXT NOT NULL,
                    crop_id TEXT NOT NULL,
                    crop_name TEXT NOT NULL,
                    category TEXT NOT NULL,
                    selected_at TEXT NOT NULL
                )
                """
            )

            connection.commit()

    def save_telemetry(self, telemetry: dict) -> int:
        """Store validated sensor telemetry."""

        received_at = datetime.now(
            timezone.utc
        ).isoformat()

        with self._get_connection() as connection:
            cursor = connection.cursor()

            cursor.execute(
                """
                INSERT INTO telemetry (
                    device_id,
                    temperature,
                    humidity,
                    soil_moisture,
                    ph,
                    mq135_raw,
                    received_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    telemetry["device_id"],
                    telemetry["temperature"],
                    telemetry["humidity"],
                    telemetry["soil_moisture"],
                    telemetry["ph"],
                    telemetry["mq135_raw"],
                    received_at,
                ),
            )

            connection.commit()

            return cursor.lastrowid

    def save_plant_configuration(
        self,
        device_id: str,
        crop: dict
    ) -> int:
        """Store a selected greenhouse crop."""

        selected_at = datetime.now(
            timezone.utc
        ).isoformat()

        with self._get_connection() as connection:
            cursor = connection.cursor()

            cursor.execute(
                """
                INSERT INTO plant_configuration (
                    device_id,
                    crop_id,
                    crop_name,
                    category,
                    selected_at
                )
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    device_id,
                    crop["crop_id"],
                    crop["name"],
                    crop["category"],
                    selected_at,
                ),
            )

            connection.commit()

            return cursor.lastrowid

    def get_latest_plant_configuration(
        self,
        device_id: str
    ):
        """Return the latest stored crop for a device."""

        with self._get_connection() as connection:
            connection.row_factory = sqlite3.Row
            cursor = connection.cursor()

            cursor.execute(
                """
                SELECT
                    crop_id,
                    crop_name,
                    category,
                    selected_at
                FROM plant_configuration
                WHERE device_id = ?
                ORDER BY id DESC
                LIMIT 1
                """,
                (device_id,),
            )

            row = cursor.fetchone()

            if row is None:
                return None

            return {
                "crop_id": row["crop_id"],
                "name": row["crop_name"],
                "category": row["category"],
                "selected_at": row["selected_at"],
            }