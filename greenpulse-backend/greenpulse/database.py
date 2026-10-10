"""
GreenPulse - Database Service

SQLite persistence layer for the GreenPulse IoT backend.

Stores:
- ESP32 telemetry
- Plant configuration
- Curated plant profiles
- Greenhouse/device location (with named location fields)
- Notification recipients and preferences
- Notification event history
- Per-alert-type state (cooldown / deduplication)
- Email delivery log

Plant profiles are obtained from the local crop catalog.
Gemini is NOT responsible for generating plant threshold values.

Migration strategy:
    All changes are non-destructive.
    ALTER TABLE statements are wrapped in try/except so they
    are safely ignored when the column already exists.
    CREATE TABLE uses IF NOT EXISTS throughout.
"""

import logging
import sqlite3
from datetime import datetime, timezone
from pathlib import Path


logger = logging.getLogger("greenpulse.database")


class Database:
    """
    SQLite database service for the GreenPulse backend.

    A new SQLite connection is created for each operation.
    This works well with GreenPulse because MQTT processing
    and AI care generation may operate in different threads.
    """

    def __init__(self, db_path="data/greenpulse.db"):
        """
        Initialize the GreenPulse database.

        Args:
            db_path:
                Location of the SQLite database file.
        """

        self.db_path = Path(db_path)

        # Create data directory if it does not exist.
        self.db_path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        # Create all required tables and run migrations.
        self._create_tables()

    # ==========================================================
    # DATABASE CONNECTION
    # ==========================================================

    def _get_connection(self):
        """
        Return a new SQLite database connection.

        WAL mode improves safety for concurrent thread access.
        """

        conn = sqlite3.connect(self.db_path)
        conn.execute("PRAGMA journal_mode=WAL")
        return conn

    # ==========================================================
    # TABLE CREATION AND MIGRATION
    # ==========================================================

    def _create_tables(self):
        """
        Create all GreenPulse tables if they do not already exist,
        and apply any required non-destructive column migrations.

        Existing tables and existing records are preserved.
        """

        connection = self._get_connection()

        try:
            cursor = connection.cursor()

            # --------------------------------------------------
            # TELEMETRY TABLE
            # --------------------------------------------------

            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS telemetry (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    device_id TEXT NOT NULL,
                    air_temperature REAL NOT NULL,
                    humidity REAL NOT NULL,
                    soil_moisture REAL NOT NULL,
                    soil_moisture_raw INTEGER NOT NULL,
                    light TEXT NOT NULL,
                    soil_temperature REAL NOT NULL,
                    received_at TEXT NOT NULL
                )
                """
            )

            # --------------------------------------------------
            # PLANT CONFIGURATION TABLE
            # --------------------------------------------------

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

            # --------------------------------------------------
            # PLANT PROFILE TABLE
            #
            # Stores validated deterministic thresholds from
            # crop_catalog.py.
            # --------------------------------------------------

            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS plant_profile (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    device_id TEXT NOT NULL,
                    plant_name TEXT NOT NULL,
                    air_temperature_min REAL NOT NULL,
                    air_temperature_max REAL NOT NULL,
                    humidity_min REAL NOT NULL,
                    humidity_max REAL NOT NULL,
                    soil_moisture_min REAL NOT NULL,
                    soil_moisture_max REAL NOT NULL,
                    soil_temperature_min REAL NOT NULL,
                    soil_temperature_max REAL NOT NULL,
                    light_preference TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
                """
            )

            # --------------------------------------------------
            # DEVICE / GREENHOUSE LOCATION TABLE
            # --------------------------------------------------

            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS device_location (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    device_id TEXT NOT NULL,
                    latitude REAL NOT NULL,
                    longitude REAL NOT NULL,
                    selected_at TEXT NOT NULL
                )
                """
            )

            # --------------------------------------------------
            # NOTIFICATION RECIPIENTS TABLE
            # --------------------------------------------------

            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS notification_recipients (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    email TEXT NOT NULL UNIQUE,
                    enabled INTEGER NOT NULL DEFAULT 1,
                    watering_alerts INTEGER NOT NULL DEFAULT 1,
                    temperature_alerts INTEGER NOT NULL DEFAULT 1,
                    humidity_alerts INTEGER NOT NULL DEFAULT 1,
                    weather_alerts INTEGER NOT NULL DEFAULT 1,
                    system_alerts INTEGER NOT NULL DEFAULT 1,
                    daily_summary INTEGER NOT NULL DEFAULT 1,
                    daily_summary_time TEXT NOT NULL DEFAULT '08:00',
                    daily_summary_timezone TEXT NOT NULL DEFAULT 'UTC',
                    last_test_email_at TEXT,
                    added_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )

            # --------------------------------------------------
            # NOTIFICATION HISTORY TABLE
            # --------------------------------------------------

            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS notification_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    notification_id TEXT NOT NULL UNIQUE,
                    device_id TEXT NOT NULL,
                    plant TEXT,
                    location TEXT,
                    type TEXT NOT NULL,
                    priority TEXT NOT NULL,
                    title TEXT NOT NULL,
                    summary TEXT NOT NULL,
                    care_tip TEXT,
                    email_status TEXT NOT NULL DEFAULT 'PENDING',
                    generated_at TEXT NOT NULL
                )
                """
            )

            # --------------------------------------------------
            # NOTIFICATION ALERT STATE TABLE
            #
            # Tracks per-alert-type state so cooldowns survive
            # backend restarts and duplicates are suppressed.
            # --------------------------------------------------

            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS notification_alert_state (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    device_id TEXT NOT NULL,
                    alert_type TEXT NOT NULL,
                    state TEXT NOT NULL DEFAULT 'NORMAL',
                    consecutive_count INTEGER NOT NULL DEFAULT 0,
                    last_triggered_at TEXT,
                    cooldown_until TEXT,
                    alert_started_at TEXT,
                    UNIQUE(device_id, alert_type)
                )
                """
            )

            # --------------------------------------------------
            # EMAIL DELIVERY LOG TABLE
            # --------------------------------------------------

            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS email_delivery_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    notification_id TEXT NOT NULL,
                    recipient_email TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'PENDING',
                    attempt_count INTEGER NOT NULL DEFAULT 0,
                    last_attempt_at TEXT,
                    accepted_at TEXT,
                    error_message TEXT,
                    UNIQUE(notification_id, recipient_email)
                )
                """
            )

            connection.commit()

            # --------------------------------------------------
            # MIGRATION: Add named location columns to
            # device_location if they do not exist yet.
            # --------------------------------------------------

            self._migrate_device_location(cursor, connection)

        finally:
            connection.close()

    def _migrate_device_location(self, cursor, connection):
        """
        Non-destructive migration: add named location columns
        to the device_location table when upgrading from
        an older GreenPulse database that only stored lat/lon.

        Safe to call multiple times — existing columns are ignored.
        """

        new_columns = [
            ("location_name", "TEXT"),
            ("admin1",        "TEXT"),
            ("country",       "TEXT"),
            ("country_code",  "TEXT"),
            ("geocoding_id",  "INTEGER"),
        ]

        for col_name, col_type in new_columns:
            try:
                cursor.execute(
                    "ALTER TABLE device_location "
                    f"ADD COLUMN {col_name} {col_type}"
                )
                connection.commit()
                logger.info(
                    "Migration applied: device_location.%s added.",
                    col_name,
                )
            except sqlite3.OperationalError:
                # Column already exists — safe to ignore.
                pass

    # ==========================================================
    # TELEMETRY
    # ==========================================================

    def save_telemetry(self, telemetry):
        """
        Save validated ESP32 telemetry.

        Expected structure:

        {
            "device_id": "device01",
            "air_temperature": 29.4,
            "humidity": 73.0,
            "soil_moisture": 42,
            "soil_moisture_raw": 2500,
            "light": "BRIGHT",
            "soil_temperature": 27.2
        }

        Returns:
            int: Inserted database record ID.
        """

        connection = self._get_connection()

        try:
            cursor = connection.cursor()
            received_at = datetime.now(timezone.utc).isoformat()

            cursor.execute(
                """
                INSERT INTO telemetry (
                    device_id, air_temperature, humidity,
                    soil_moisture, soil_moisture_raw,
                    light, soil_temperature, received_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    telemetry["device_id"],
                    telemetry["air_temperature"],
                    telemetry["humidity"],
                    telemetry["soil_moisture"],
                    telemetry["soil_moisture_raw"],
                    telemetry["light"],
                    telemetry["soil_temperature"],
                    received_at,
                ),
            )

            connection.commit()
            return cursor.lastrowid

        finally:
            connection.close()

    # ==========================================================
    # PLANT CONFIGURATION
    # ==========================================================

    def save_plant_configuration(self, device_id, crop):
        """
        Save the plant selected for a GreenPulse device.

        Expected crop structure:

        {
            "crop_id": "tomato",
            "name": "Tomato",
            "category": "Greenhouse Crop"
        }

        Returns:
            int: Inserted database record ID.
        """

        connection = self._get_connection()

        try:
            cursor = connection.cursor()
            selected_at = datetime.now(timezone.utc).isoformat()

            cursor.execute(
                """
                INSERT INTO plant_configuration (
                    device_id, crop_id, crop_name, category, selected_at
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

        finally:
            connection.close()

    def get_latest_plant_configuration(self, device_id):
        """
        Return the latest selected plant configuration.

        Both database-style and application-style naming
        formats are returned for compatibility with the
        existing GreenPulse services.

        Returns:
            dict | None
        """

        connection = self._get_connection()

        try:
            cursor = connection.cursor()

            cursor.execute(
                """
                SELECT crop_id, crop_name, category, selected_at
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
                # Database-style names
                "crop_id":   row[0],
                "crop_name": row[1],
                # Application-style aliases
                "id":        row[0],
                "name":      row[1],
                "category":  row[2],
                "selected_at": row[3],
            }

        finally:
            connection.close()

    # ==========================================================
    # PLANT PROFILE
    # ==========================================================

    def save_plant_profile(self, device_id, profile):
        """
        Save a validated plant profile from crop_catalog.py.

        Returns:
            int: Inserted database record ID.
        """

        connection = self._get_connection()

        try:
            cursor = connection.cursor()
            created_at = datetime.now(timezone.utc).isoformat()

            cursor.execute(
                """
                INSERT INTO plant_profile (
                    device_id, plant_name,
                    air_temperature_min, air_temperature_max,
                    humidity_min, humidity_max,
                    soil_moisture_min, soil_moisture_max,
                    soil_temperature_min, soil_temperature_max,
                    light_preference, created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    device_id,
                    profile["plant"],
                    profile["air_temperature"]["min"],
                    profile["air_temperature"]["max"],
                    profile["humidity"]["min"],
                    profile["humidity"]["max"],
                    profile["soil_moisture"]["min"],
                    profile["soil_moisture"]["max"],
                    profile["soil_temperature"]["min"],
                    profile["soil_temperature"]["max"],
                    profile["light_preference"],
                    created_at,
                ),
            )

            connection.commit()
            return cursor.lastrowid

        finally:
            connection.close()

    def get_latest_plant_profile(self, device_id):
        """
        Return the latest validated plant profile stored
        for a GreenPulse device.

        Returns:
            dict | None
        """

        connection = self._get_connection()

        try:
            cursor = connection.cursor()

            cursor.execute(
                """
                SELECT
                    plant_name,
                    air_temperature_min, air_temperature_max,
                    humidity_min, humidity_max,
                    soil_moisture_min, soil_moisture_max,
                    soil_temperature_min, soil_temperature_max,
                    light_preference, created_at
                FROM plant_profile
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
                "plant": row[0],
                "air_temperature": {"min": row[1], "max": row[2]},
                "humidity":        {"min": row[3], "max": row[4]},
                "soil_moisture":   {"min": row[5], "max": row[6]},
                "soil_temperature": {"min": row[7], "max": row[8]},
                "light_preference": row[9],
                "created_at":       row[10],
            }

        finally:
            connection.close()

    # ==========================================================
    # DEVICE / GREENHOUSE LOCATION
    # ==========================================================

    def save_device_location(self, location):
        """
        Save a validated greenhouse/device location.

        Accepts both the legacy coordinate-only format and
        the new named-location format from the autocomplete.

        Minimum required keys: device_id, latitude, longitude.
        Extended keys (optional): location_name, admin1,
            country, country_code, geocoding_id.

        Returns:
            int: Inserted database record ID.
        """

        connection = self._get_connection()

        try:
            cursor = connection.cursor()
            selected_at = datetime.now(timezone.utc).isoformat()

            cursor.execute(
                """
                INSERT INTO device_location (
                    device_id, latitude, longitude,
                    location_name, admin1, country,
                    country_code, geocoding_id, selected_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    location["device_id"],
                    location["latitude"],
                    location["longitude"],
                    location.get("location_name"),
                    location.get("admin1"),
                    location.get("country"),
                    location.get("country_code"),
                    location.get("geocoding_id"),
                    selected_at,
                ),
            )

            connection.commit()
            return cursor.lastrowid

        finally:
            connection.close()

    def get_latest_device_location(self, device_id):
        """
        Return the latest greenhouse/device location.

        Returns both coordinate and named location fields
        when available.

        Returns:
            dict | None
        """

        connection = self._get_connection()

        try:
            cursor = connection.cursor()

            cursor.execute(
                """
                SELECT
                    device_id, latitude, longitude,
                    location_name, admin1, country,
                    country_code, geocoding_id, selected_at
                FROM device_location
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
                "device_id":     row[0],
                "latitude":      row[1],
                "longitude":     row[2],
                "location_name": row[3],
                "admin1":        row[4],
                "country":       row[5],
                "country_code":  row[6],
                "geocoding_id":  row[7],
                "selected_at":   row[8],
            }

        finally:
            connection.close()

    # ==========================================================
    # NOTIFICATION RECIPIENTS
    # ==========================================================

    def add_notification_recipient(
        self,
        email: str,
        preferences: dict = None,
    ) -> int:
        """
        Add a new notification recipient.

        Raises ValueError if email already exists.

        Returns:
            int: Inserted record ID.
        """

        if preferences is None:
            preferences = {}

        now = datetime.now(timezone.utc).isoformat()
        connection = self._get_connection()

        try:
            cursor = connection.cursor()

            cursor.execute(
                """
                INSERT INTO notification_recipients (
                    email, enabled,
                    watering_alerts, temperature_alerts,
                    humidity_alerts, weather_alerts,
                    system_alerts, daily_summary,
                    daily_summary_time, daily_summary_timezone,
                    added_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    email.strip().lower(),
                    1 if preferences.get("enabled", True) else 0,
                    1 if preferences.get("watering_alerts", True) else 0,
                    1 if preferences.get("temperature_alerts", True) else 0,
                    1 if preferences.get("humidity_alerts", True) else 0,
                    1 if preferences.get("weather_alerts", True) else 0,
                    1 if preferences.get("system_alerts", True) else 0,
                    1 if preferences.get("daily_summary", True) else 0,
                    preferences.get("daily_summary_time", "08:00"),
                    preferences.get("daily_summary_timezone", "UTC"),
                    now,
                    now,
                ),
            )

            connection.commit()
            return cursor.lastrowid

        except sqlite3.IntegrityError:
            raise ValueError(
                f"Recipient already exists: {email}"
            )

        finally:
            connection.close()

    def update_recipient_preferences(
        self,
        email: str,
        preferences: dict,
    ) -> bool:
        """
        Update notification preferences for a recipient.

        Returns:
            bool: True if the recipient was found and updated.
        """

        now = datetime.now(timezone.utc).isoformat()
        connection = self._get_connection()

        try:
            cursor = connection.cursor()

            cursor.execute(
                """
                UPDATE notification_recipients SET
                    enabled = ?,
                    watering_alerts = ?,
                    temperature_alerts = ?,
                    humidity_alerts = ?,
                    weather_alerts = ?,
                    system_alerts = ?,
                    daily_summary = ?,
                    daily_summary_time = ?,
                    daily_summary_timezone = ?,
                    updated_at = ?
                WHERE email = ?
                """,
                (
                    1 if preferences.get("enabled", True) else 0,
                    1 if preferences.get("watering_alerts", True) else 0,
                    1 if preferences.get("temperature_alerts", True) else 0,
                    1 if preferences.get("humidity_alerts", True) else 0,
                    1 if preferences.get("weather_alerts", True) else 0,
                    1 if preferences.get("system_alerts", True) else 0,
                    1 if preferences.get("daily_summary", True) else 0,
                    preferences.get("daily_summary_time", "08:00"),
                    preferences.get("daily_summary_timezone", "UTC"),
                    now,
                    email.strip().lower(),
                ),
            )

            connection.commit()
            return cursor.rowcount > 0

        finally:
            connection.close()

    def remove_notification_recipient(self, email: str) -> bool:
        """
        Remove a notification recipient.

        Returns:
            bool: True if a record was deleted.
        """

        connection = self._get_connection()

        try:
            cursor = connection.cursor()

            cursor.execute(
                "DELETE FROM notification_recipients WHERE email = ?",
                (email.strip().lower(),),
            )

            connection.commit()
            return cursor.rowcount > 0

        finally:
            connection.close()

    def get_all_notification_recipients(self) -> list:
        """Return all configured notification recipients."""

        connection = self._get_connection()

        try:
            cursor = connection.cursor()

            cursor.execute(
                """
                SELECT
                    id, email, enabled,
                    watering_alerts, temperature_alerts, humidity_alerts,
                    weather_alerts, system_alerts, daily_summary,
                    daily_summary_time, daily_summary_timezone,
                    last_test_email_at, added_at, updated_at
                FROM notification_recipients
                ORDER BY added_at ASC
                """
            )

            return [
                {
                    "id":                     row[0],
                    "email":                  row[1],
                    "enabled":                bool(row[2]),
                    "watering_alerts":        bool(row[3]),
                    "temperature_alerts":     bool(row[4]),
                    "humidity_alerts":        bool(row[5]),
                    "weather_alerts":         bool(row[6]),
                    "system_alerts":          bool(row[7]),
                    "daily_summary":          bool(row[8]),
                    "daily_summary_time":     row[9],
                    "daily_summary_timezone": row[10],
                    "last_test_email_at":     row[11],
                    "added_at":               row[12],
                    "updated_at":             row[13],
                }
                for row in cursor.fetchall()
            ]

        finally:
            connection.close()

    def get_recipients_for_alert_type(
        self,
        alert_type: str,
    ) -> list:
        """
        Return enabled recipients subscribed to a given alert
        category.

        alert_type must be one of:
            WATERING, TEMPERATURE, HUMIDITY, WEATHER,
            SYSTEM, RECOVERY, DAILY_SUMMARY
        """

        column_map = {
            "WATERING":      "watering_alerts",
            "TEMPERATURE":   "temperature_alerts",
            "HUMIDITY":      "humidity_alerts",
            "WEATHER":       "weather_alerts",
            "SYSTEM":        "system_alerts",
            "RECOVERY":      "system_alerts",
            "DAILY_SUMMARY": "daily_summary",
        }

        column = column_map.get(alert_type.upper())

        if column is None:
            return []

        connection = self._get_connection()

        try:
            cursor = connection.cursor()

            cursor.execute(
                f"""
                SELECT email FROM notification_recipients
                WHERE enabled = 1 AND {column} = 1
                """
            )

            return [row[0] for row in cursor.fetchall()]

        finally:
            connection.close()

    def update_last_test_email(self, email: str):
        """Record the timestamp of the most recent test email."""

        now = datetime.now(timezone.utc).isoformat()
        connection = self._get_connection()

        try:
            cursor = connection.cursor()

            cursor.execute(
                """
                UPDATE notification_recipients
                SET last_test_email_at = ?
                WHERE email = ?
                """,
                (now, email.strip().lower()),
            )

            connection.commit()

        finally:
            connection.close()

    def get_recipient_by_email(self, email: str) -> dict | None:
        """Return a single recipient record, or None."""

        connection = self._get_connection()

        try:
            cursor = connection.cursor()

            cursor.execute(
                """
                SELECT
                    id, email, enabled,
                    watering_alerts, temperature_alerts, humidity_alerts,
                    weather_alerts, system_alerts, daily_summary,
                    daily_summary_time, daily_summary_timezone,
                    last_test_email_at, added_at, updated_at
                FROM notification_recipients
                WHERE email = ?
                """,
                (email.strip().lower(),),
            )

            row = cursor.fetchone()

            if row is None:
                return None

            return {
                "id":                     row[0],
                "email":                  row[1],
                "enabled":                bool(row[2]),
                "watering_alerts":        bool(row[3]),
                "temperature_alerts":     bool(row[4]),
                "humidity_alerts":        bool(row[5]),
                "weather_alerts":         bool(row[6]),
                "system_alerts":          bool(row[7]),
                "daily_summary":          bool(row[8]),
                "daily_summary_time":     row[9],
                "daily_summary_timezone": row[10],
                "last_test_email_at":     row[11],
                "added_at":               row[12],
                "updated_at":             row[13],
            }

        finally:
            connection.close()

    # ==========================================================
    # NOTIFICATION HISTORY
    # ==========================================================

    def save_notification(self, notification: dict) -> bool:
        """
        Store a notification event in history.

        Uses INSERT OR IGNORE so duplicate notification_ids
        from a backend restart do not create duplicate rows.

        Returns:
            bool: True if a new row was inserted.
        """

        connection = self._get_connection()

        try:
            cursor = connection.cursor()

            cursor.execute(
                """
                INSERT OR IGNORE INTO notification_history (
                    notification_id, device_id, plant, location,
                    type, priority, title, summary, care_tip,
                    email_status, generated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    notification["notification_id"],
                    notification["device_id"],
                    notification.get("plant"),
                    notification.get("location"),
                    notification["type"],
                    notification["priority"],
                    notification["title"],
                    notification["summary"],
                    notification.get("care_tip"),
                    notification.get("email_status", "PENDING"),
                    notification["generated_at"],
                ),
            )

            connection.commit()
            return cursor.rowcount > 0

        finally:
            connection.close()

    def update_notification_email_status(
        self,
        notification_id: str,
        email_status: str,
    ):
        """Update the email delivery status of a notification."""

        connection = self._get_connection()

        try:
            cursor = connection.cursor()

            cursor.execute(
                """
                UPDATE notification_history
                SET email_status = ?
                WHERE notification_id = ?
                """,
                (email_status, notification_id),
            )

            connection.commit()

        finally:
            connection.close()

    def get_recent_notifications(
        self,
        device_id: str,
        limit: int = 20,
    ) -> list:
        """Return recent notifications ordered newest-first."""

        connection = self._get_connection()

        try:
            cursor = connection.cursor()

            cursor.execute(
                """
                SELECT
                    notification_id, device_id, plant, location,
                    type, priority, title, summary, care_tip,
                    email_status, generated_at
                FROM notification_history
                WHERE device_id = ?
                ORDER BY generated_at DESC
                LIMIT ?
                """,
                (device_id, limit),
            )

            return [
                {
                    "notification_id": row[0],
                    "device_id":       row[1],
                    "plant":           row[2],
                    "location":        row[3],
                    "type":            row[4],
                    "priority":        row[5],
                    "title":           row[6],
                    "summary":         row[7],
                    "care_tip":        row[8],
                    "email_status":    row[9],
                    "generated_at":    row[10],
                }
                for row in cursor.fetchall()
            ]

        finally:
            connection.close()

    # ==========================================================
    # NOTIFICATION ALERT STATE
    # ==========================================================

    def get_alert_state(
        self,
        device_id: str,
        alert_type: str,
    ) -> dict:
        """
        Return the current alert state for a device/alert-type
        combination, or a default NORMAL state if none exists.
        """

        connection = self._get_connection()

        try:
            cursor = connection.cursor()

            cursor.execute(
                """
                SELECT state, consecutive_count, last_triggered_at,
                       cooldown_until, alert_started_at
                FROM notification_alert_state
                WHERE device_id = ? AND alert_type = ?
                """,
                (device_id, alert_type),
            )

            row = cursor.fetchone()

            if row is None:
                return {
                    "state":             "NORMAL",
                    "consecutive_count": 0,
                    "last_triggered_at": None,
                    "cooldown_until":    None,
                    "alert_started_at":  None,
                }

            return {
                "state":             row[0],
                "consecutive_count": row[1],
                "last_triggered_at": row[2],
                "cooldown_until":    row[3],
                "alert_started_at":  row[4],
            }

        finally:
            connection.close()

    def save_alert_state(
        self,
        device_id: str,
        alert_type: str,
        state: dict,
    ):
        """
        Insert or replace the alert state for a
        device/alert-type combination.
        """

        connection = self._get_connection()

        try:
            cursor = connection.cursor()

            cursor.execute(
                """
                INSERT INTO notification_alert_state (
                    device_id, alert_type, state, consecutive_count,
                    last_triggered_at, cooldown_until, alert_started_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(device_id, alert_type) DO UPDATE SET
                    state = excluded.state,
                    consecutive_count = excluded.consecutive_count,
                    last_triggered_at = excluded.last_triggered_at,
                    cooldown_until = excluded.cooldown_until,
                    alert_started_at = excluded.alert_started_at
                """,
                (
                    device_id,
                    alert_type,
                    state.get("state", "NORMAL"),
                    state.get("consecutive_count", 0),
                    state.get("last_triggered_at"),
                    state.get("cooldown_until"),
                    state.get("alert_started_at"),
                ),
            )

            connection.commit()

        finally:
            connection.close()

    # ==========================================================
    # EMAIL DELIVERY LOG
    # ==========================================================

    def log_email_attempt(
        self,
        notification_id: str,
        recipient_email: str,
        status: str,
        error_message: str = None,
    ):
        """
        Record an email delivery attempt.

        Inserts on first call; updates attempt_count on retries.
        """

        now = datetime.now(timezone.utc).isoformat()
        accepted_at = now if status == "ACCEPTED_BY_SMTP" else None

        connection = self._get_connection()

        try:
            cursor = connection.cursor()

            cursor.execute(
                """
                INSERT INTO email_delivery_log (
                    notification_id, recipient_email, status,
                    attempt_count, last_attempt_at,
                    accepted_at, error_message
                )
                VALUES (?, ?, ?, 1, ?, ?, ?)
                ON CONFLICT(notification_id, recipient_email)
                DO UPDATE SET
                    status = excluded.status,
                    attempt_count = attempt_count + 1,
                    last_attempt_at = excluded.last_attempt_at,
                    accepted_at = CASE
                        WHEN excluded.status = 'ACCEPTED_BY_SMTP'
                        THEN excluded.last_attempt_at
                        ELSE accepted_at
                    END,
                    error_message = excluded.error_message
                """,
                (
                    notification_id,
                    recipient_email,
                    status,
                    now,
                    accepted_at,
                    error_message,
                ),
            )

            connection.commit()

        finally:
            connection.close()

    def notification_already_sent(
        self,
        notification_id: str,
        recipient_email: str,
    ) -> bool:
        """
        Return True if SMTP already accepted this notification
        for this recipient.

        Used to prevent duplicate emails on backend restart.
        """

        connection = self._get_connection()

        try:
            cursor = connection.cursor()

            cursor.execute(
                """
                SELECT 1 FROM email_delivery_log
                WHERE notification_id = ?
                AND recipient_email = ?
                AND status = 'ACCEPTED_BY_SMTP'
                LIMIT 1
                """,
                (notification_id, recipient_email),
            )

            return cursor.fetchone() is not None

        finally:
            connection.close()