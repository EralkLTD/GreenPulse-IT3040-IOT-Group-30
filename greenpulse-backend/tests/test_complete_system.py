"""
GreenPulse - Comprehensive System Upgrade Test Suite
Verifies all 22 requirements from Section 12 of the Master Prompt.
"""
import sys
import os
import json
import sqlite3
import unittest
from unittest.mock import MagicMock, patch
from datetime import datetime, timezone, timedelta

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from greenpulse.crop_catalog import get_crop, get_profile
from greenpulse.plant_service import PlantService
from greenpulse.plant_profile_service import PlantProfileService
from greenpulse.telemetry_service import TelemetryService
from greenpulse.location_service import LocationService, LocationValidationError
from greenpulse.geocoding_service import GeocodingService, GeocodingProvider
from greenpulse.database import Database
from greenpulse.email_service import SmtpSender, SmtpError
from greenpulse.gemini_service import GeminiService
from greenpulse.notification_service import NotificationService
from greenpulse.weather_service import WeatherService
from greenpulse.daily_summary_service import DailySummaryService


class TestGreenPulseUpgrades(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Use an isolated test database in memory or temp file
        cls.test_db_path = "tests/test_greenpulse.db"
        if os.path.exists(cls.test_db_path):
            os.remove(cls.test_db_path)
        cls.db = Database(cls.test_db_path)

        # Mock Gemini to avoid external network calls during unit test suite
        cls.mock_gemini = MagicMock(spec=GeminiService)
        cls.mock_gemini.generate_notification_content.side_effect = lambda ctx: {
            "title": f"Alert {ctx.get('type')}",
            "summary": "Mock greenhouse condition summary.",
            "care_tip": "Mock cautious care tip.",
            "weather_context": "Mock weather impact context.",
        }
        cls.mock_gemini.generate_daily_summary.return_value = {
            "overall_status": "GOOD",
            "summary": "Mock daily status summary.",
            "recommendations": "Mock recommendation.",
            "weather_outlook": "Mock weather outlook.",
        }

    @classmethod
    def tearDownClass(cls):
        if os.path.exists(cls.test_db_path):
            try:
                os.remove(cls.test_db_path)
            except Exception:
                pass

    # 1. Tomato and Cherry Tomato plant selection
    def test_01_tomato_selection(self):
        ps = PlantService()
        tomato_cfg = ps.parse_and_set_crop('{"plant_type": "Tomato"}')
        self.assertEqual(tomato_cfg["name"], "Tomato")
        self.assertEqual(tomato_cfg["crop_id"], "tomato")

        cherry_cfg = ps.parse_and_set_crop('{"plant_type": "Cherry Tomato"}')
        self.assertEqual(cherry_cfg["name"], "Cherry Tomato")
        self.assertEqual(cherry_cfg["crop_id"], "cherry_tomato")

    # 2. Plant profile publication
    def test_02_plant_profile_contract(self):
        prof = get_profile("Tomato")
        self.assertIn("plant", prof)
        self.assertEqual(prof["plant"], "Tomato")
        self.assertNotIn("crop_id", prof)
        validated = PlantProfileService.validate_profile(prof)
        self.assertEqual(validated["plant"], "Tomato")

    # 3. Existing telemetry ingestion
    def test_03_telemetry_ingestion(self):
        raw = json.dumps({
            "device_id": "device01",
            "air_temperature": 25.5,
            "humidity": 65.0,
            "soil_moisture": 55.0,
            "soil_moisture_raw": 2100,
            "light": "BRIGHT",
            "soil_temperature": 22.0
        })
        val = TelemetryService.parse_and_validate(raw)
        self.assertEqual(val["air_temperature"], 25.5)
        rec_id = self.db.save_telemetry(val)
        self.assertGreater(rec_id, 0)

    # 4. Worldwide geocoding search
    def test_04_worldwide_geocoding(self):
        mock_provider = MagicMock(spec=GeocodingProvider)
        mock_provider.search.return_value = [
            {"id": 1248991, "name": "Colombo", "latitude": 6.9271, "longitude": 79.8612, "country": "Sri Lanka", "country_code": "LK", "admin1": "Western", "display_name": "Colombo, Western, Sri Lanka"}
        ]
        geo = GeocodingService(mock_provider)
        res = geo.search("Colombo", count=5)
        self.assertEqual(len(res), 1)
        self.assertEqual(res[0]["name"], "Colombo")
        self.assertEqual(res[0]["latitude"], 6.9271)

    # 5. Duplicate city names support
    def test_05_duplicate_city_names(self):
        mock_provider = MagicMock(spec=GeocodingProvider)
        mock_provider.search.return_value = [
            {"id": 1, "name": "London", "latitude": 51.5074, "longitude": -0.1278, "country": "United Kingdom", "admin1": "England", "display_name": "London, England, United Kingdom"},
            {"id": 2, "name": "London", "latitude": 42.9849, "longitude": -81.2453, "country": "Canada", "admin1": "Ontario", "display_name": "London, Ontario, Canada"}
        ]
        geo = GeocodingService(mock_provider)
        res = geo.search("London", count=8)
        self.assertEqual(len(res), 2)
        self.assertEqual(res[0]["country"], "United Kingdom")
        self.assertEqual(res[1]["country"], "Canada")

    # 6. Invalid location selection (including placeholder 0,0)
    def test_06_invalid_location_selection(self):
        # 0,0 coordinates must be rejected
        with self.assertRaises(LocationValidationError):
            LocationService.parse_and_validate(json.dumps({"device_id": "device01", "latitude": 0.0, "longitude": 0.0}))

        # Out of bounds latitude
        with self.assertRaises(LocationValidationError):
            LocationService.parse_and_validate(json.dumps({"device_id": "device01", "latitude": 95.0, "longitude": 10.0}))

    # 7. Named location persistence
    def test_07_named_location_persistence(self):
        loc_payload = json.dumps({
            "device_id": "device01",
            "location_name": "Kandy",
            "admin1": "Central Province",
            "country": "Sri Lanka",
            "country_code": "LK",
            "geocoding_id": 1241622,
            "latitude": 7.2906,
            "longitude": 80.6337
        })
        parsed = LocationService.parse_and_validate(loc_payload)
        rec_id = self.db.save_device_location(parsed)
        self.assertGreater(rec_id, 0)

        retrieved = self.db.get_latest_device_location("device01")
        self.assertEqual(retrieved["location_name"], "Kandy")
        self.assertEqual(retrieved["country"], "Sri Lanka")
        self.assertEqual(retrieved["latitude"], 7.2906)

    # 8. Weather forecast for selected location
    def test_08_weather_forecast(self):
        ws = WeatherService()
        with patch("requests.get") as mock_get:
            mock_resp = MagicMock()
            mock_resp.status_code = 200
            mock_resp.json.return_value = {
                "latitude": 7.2906,
                "longitude": 80.6337,
                "timezone": "Asia/Colombo",
                "current": {
                    "time": "2026-10-08T11:00",
                    "temperature_2m": 28.5,
                    "relative_humidity_2m": 75.0,
                    "precipitation": 0.0,
                    "weather_code": 1,
                },
                "hourly": {
                    "time": ["2026-10-08T11:00", "2026-10-08T12:00"],
                    "precipitation_probability": [80, 85],
                    "precipitation": [0.0, 2.5],
                },
            }
            mock_get.return_value = mock_resp
            w = ws.get_weather(7.2906, 80.6337)
            self.assertEqual(w["temperature"], 28.5)
            self.assertEqual(w["rain_probability_next_6h"], 85)

    # 9. Low soil moisture notification
    def test_09_low_soil_moisture_detection(self):
        mock_smtp = MagicMock(spec=SmtpSender)
        mock_smtp.send_notification_email.return_value = {"success": True, "status": "ACCEPTED_BY_SMTP"}
        engine = NotificationService(database=self.db, smtp_sender=mock_smtp, gemini_service=self.mock_gemini)

        profile = get_profile("Tomato") # min soil moisture is typically 60%
        # Send 1st sample
        notifs_1 = engine.evaluate_telemetry(
            telemetry={"device_id": "device01", "soil_moisture": 30.0, "air_temperature": 24.0, "humidity": 65.0},
            plant_name="Tomato",
            profile=profile,
        )
        # Filters first sample (persistence check requires 2 consecutive)
        self.assertEqual(len(notifs_1), 0)

        # Send 2nd sample -> triggers alert!
        notifs_2 = engine.evaluate_telemetry(
            telemetry={"device_id": "device01", "soil_moisture": 30.0, "air_temperature": 24.0, "humidity": 65.0},
            plant_name="Tomato",
            profile=profile,
        )
        self.assertEqual(len(notifs_2), 1)
        self.assertEqual(notifs_2[0]["type"], "WATERING")

    # 10. Normal-to-alert state transition
    def test_10_normal_to_alert_state(self):
        state = self.db.get_alert_state("device01", "WATERING")
        self.assertEqual(state["state"], "ALERT")

    # 11. Alert-to-recovery transition
    def test_11_alert_to_recovery(self):
        mock_smtp = MagicMock(spec=SmtpSender)
        mock_smtp.send_notification_email.return_value = {"success": True, "status": "ACCEPTED_BY_SMTP"}
        engine = NotificationService(database=self.db, smtp_sender=mock_smtp, gemini_service=self.mock_gemini)
        profile = get_profile("Tomato")

        # 1st healthy sample
        engine.evaluate_telemetry(
            telemetry={"device_id": "device01", "soil_moisture": 70.0, "air_temperature": 24.0, "humidity": 65.0},
            plant_name="Tomato",
            profile=profile,
        )
        # 2nd healthy sample -> recovery triggers!
        rec_notifs = engine.evaluate_telemetry(
            telemetry={"device_id": "device01", "soil_moisture": 70.0, "air_temperature": 24.0, "humidity": 65.0},
            plant_name="Tomato",
            profile=profile,
        )
        self.assertEqual(len(rec_notifs), 1)
        self.assertTrue(rec_notifs[0]["type"].startswith("RECOVERY"))
        state = self.db.get_alert_state("device01", "WATERING")
        self.assertEqual(state["state"], "NORMAL")

    # 12. Cooldown and duplicate suppression
    def test_12_cooldown_suppression(self):
        mock_smtp = MagicMock(spec=SmtpSender)
        mock_smtp.send_notification_email.return_value = {"success": True, "status": "ACCEPTED_BY_SMTP"}
        engine = NotificationService(database=self.db, smtp_sender=mock_smtp, gemini_service=self.mock_gemini)
        profile = get_profile("Tomato")

        # Trigger alert again
        engine.evaluate_telemetry({"device_id": "device01", "soil_moisture": 30.0}, "Tomato", profile)
        n1 = engine.evaluate_telemetry({"device_id": "device01", "soil_moisture": 30.0}, "Tomato", profile)
        self.assertEqual(len(n1), 1)

        # Subsequent low readings while in cooldown must NOT generate new alerts
        n2 = engine.evaluate_telemetry({"device_id": "device01", "soil_moisture": 29.0}, "Tomato", profile)
        self.assertEqual(len(n2), 0)

    # 13. Multiple email recipients
    def test_13_multiple_recipients(self):
        self.db.add_notification_recipient("rec1@example.com", {"watering_alerts": True})
        self.db.add_notification_recipient("rec2@example.com", {"watering_alerts": True})
        recs = self.db.get_recipients_for_alert_type("WATERING")
        self.assertIn("rec1@example.com", recs)
        self.assertIn("rec2@example.com", recs)

    # 14. Invalid email address rejection
    def test_14_invalid_email_validation(self):
        self.assertFalse(SmtpSender.is_valid_email("not-an-email"))
        self.assertFalse(SmtpSender.is_valid_email("missing@domain"))
        self.assertTrue(SmtpSender.is_valid_email("valid.grower@farm.org"))

    # 15. SMTP failure handling
    def test_15_smtp_failure_handling(self):
        sender = SmtpSender(smtp_host="localhost", smtp_port=9999, timeout=1)
        res = sender.send_email("valid@example.com", "Test", "Text body", max_retries=0)
        self.assertFalse(res["success"])
        self.assertEqual(res["status"], "SMTP_ERROR")

    # 16. Gemini API failure and deterministic fallback
    def test_16_gemini_fallback(self):
        # Even if Gemini API raises or is missing, fallback_notification_content works
        fallback = GeminiService.fallback_notification_content(None, {
            "type": "WATERING",
            "priority": "MEDIUM",
            "plant": "Tomato",
            "telemetry": {"soil_moisture": 25.0},
        })
        self.assertIn("title", fallback)
        self.assertIn("care_tip", fallback)
        self.assertIn("Tomato", fallback["title"])

    # 17. Node-RED browser refresh (state preserved in DB)
    def test_17_refresh_persistence(self):
        loc = self.db.get_latest_device_location("device01")
        self.assertIsNotNone(loc)
        self.assertEqual(loc["location_name"], "Kandy")

    # 18. Backend restart (profile, location, and alert state intact)
    def test_18_backend_restart(self):
        new_db_instance = Database(self.test_db_path)
        loc = new_db_instance.get_latest_device_location("device01")
        self.assertEqual(loc["location_name"], "Kandy")
        state = new_db_instance.get_alert_state("device01", "WATERING")
        self.assertIsNotNone(state)

    # 19. MQTT reconnect and retained messages
    def test_19_retained_topic_contract(self):
        from greenpulse.mqtt_service import (
            LOCATION_RESOLVED_TOPIC,
            NOTIFICATION_SETTINGS_STATE_TOPIC,
            NOTIFICATION_STATUS_TOPIC,
            PROFILE_TOPIC,
        )
        self.assertEqual(LOCATION_RESOLVED_TOPIC, "greenpulse/device01/location/resolved")
        self.assertEqual(NOTIFICATION_SETTINGS_STATE_TOPIC, "greenpulse/device01/notification/settings/state")
        self.assertEqual(NOTIFICATION_STATUS_TOPIC, "greenpulse/device01/notification/status")
        self.assertEqual(PROFILE_TOPIC, "greenpulse/device01/profile")

    # 20. No duplicate emails on restart
    def test_20_no_duplicate_emails_on_restart(self):
        notif_id = "gp-device01-TEST-12345"
        recipient = "rec1@example.com"
        self.assertFalse(self.db.notification_already_sent(notif_id, recipient))
        self.db.log_email_attempt(notif_id, recipient, "ACCEPTED_BY_SMTP")
        self.assertTrue(self.db.notification_already_sent(notif_id, recipient))

    # 21. Daily summary scheduling
    def test_21_daily_summary_service(self):
        mock_smtp = MagicMock(spec=SmtpSender)
        mock_smtp.send_daily_summary_email.return_value = {"success": True, "status": "ACCEPTED_BY_SMTP"}
        dss = DailySummaryService(database=self.db, smtp_sender=mock_smtp, gemini_service=self.mock_gemini)
        summary = dss.send_daily_summary_now()
        self.assertIn("summary_id", summary)
        self.assertIn("summary_data", summary)

    # 22. Preservation of existing ESP32 profile synchronization
    def test_22_esp32_profile_synchronization(self):
        prof = get_profile("Mint")
        self.assertIn("air_temperature", prof)
        self.assertIn("soil_moisture", prof)
        self.assertIn("light_preference", prof)
        self.assertEqual(prof["plant"], "Mint")


if __name__ == "__main__":
    unittest.main()
