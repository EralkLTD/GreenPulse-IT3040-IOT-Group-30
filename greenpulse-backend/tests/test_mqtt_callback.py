"""
GreenPulse — Unit Tests: MQTT Callback Registration & Crop Config Flow

Tests verify:
1. on_message is registered on the client.
2. Valid crop config is received, persisted, and triggers profile publication.
3. Malformed JSON is rejected safely.
4. Unsupported crop names are rejected.
5. Crop persists across restarts (database round-trip).
6. Published profile uses QoS 1 + retain.
7. Reconnect re-subscribes all four topics.
"""
import json
import os
import sys
import unittest
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from greenpulse.plant_service import PlantService, PlantConfigError
from greenpulse.database import Database
from greenpulse.crop_catalog import get_profile
from greenpulse.plant_profile_service import PlantProfileService, PlantProfileValidationError


def _make_fake_message(topic: str, payload: str):
    msg = MagicMock()
    msg.topic = topic
    msg.payload = payload.encode("utf-8")
    return msg


def _make_mqtt_service():
    with patch("greenpulse.mqtt_service.Config.validate"), \
         patch("greenpulse.mqtt_service.Database") as MockDB, \
         patch("greenpulse.mqtt_service.GeminiService"), \
         patch("greenpulse.mqtt_service.CareService"), \
         patch("greenpulse.mqtt_service.NotificationService") as MockNS, \
         patch("greenpulse.mqtt_service.DailySummaryService") as MockDS, \
         patch("greenpulse.mqtt_service.mqtt") as mock_mqtt_module:

        mock_client = MagicMock()
        mock_client.subscribe.return_value = (0, 1)
        mock_client.publish.return_value = MagicMock(rc=0, mid=99)
        mock_mqtt_module.Client.return_value = mock_client
        mock_mqtt_module.MQTT_ERR_SUCCESS = 0
        mock_mqtt_module.CallbackAPIVersion.VERSION2 = 2

        mock_db = MockDB.return_value
        mock_db.get_latest_plant_configuration.return_value = None
        mock_db.get_latest_plant_profile.return_value = None
        mock_db.get_latest_device_location.return_value = None
        mock_db.save_plant_configuration.return_value = 42
        mock_db.save_plant_profile.return_value = 43

        mock_ns = MockNS.return_value
        mock_ns.get_recipients.return_value = []
        mock_ns.get_recent_notifications.return_value = []

        from greenpulse.mqtt_service import MQTTService
        svc = MQTTService()
        return svc, mock_client, mock_db


class TestCallbackRegistration(unittest.TestCase):

    def test_on_message_is_registered(self):
        svc, mock_client, _ = _make_mqtt_service()
        self.assertEqual(
            mock_client.on_message, svc._on_message,
            "client.on_message must point to MQTTService._on_message"
        )

    def test_on_connect_is_registered(self):
        svc, mock_client, _ = _make_mqtt_service()
        self.assertEqual(mock_client.on_connect, svc._on_connect)

    def test_on_disconnect_is_registered(self):
        svc, mock_client, _ = _make_mqtt_service()
        self.assertEqual(mock_client.on_disconnect, svc._on_disconnect)

    def test_on_subscribe_is_registered(self):
        svc, mock_client, _ = _make_mqtt_service()
        self.assertEqual(mock_client.on_subscribe, svc._on_subscribe)


class TestCropConfigProcessing(unittest.TestCase):

    def setUp(self):
        self.svc, self.mock_client, self.mock_db = _make_mqtt_service()

    def _dispatch(self, topic: str, payload: str):
        msg = _make_fake_message(topic, payload)
        self.svc._on_message(client=None, userdata=None, message=msg)

    def test_valid_tomato_config_saves_and_publishes(self):
        self._dispatch("greenpulse/device01/config", '{"plant_type": "Tomato"}')
        self.mock_db.save_plant_configuration.assert_called_once()
        crop_arg = self.mock_db.save_plant_configuration.call_args[0][1]
        self.assertEqual(crop_arg["name"], "Tomato")
        self.mock_db.save_plant_profile.assert_called_once()
        profile_calls = [
            c for c in self.mock_client.publish.call_args_list
            if "greenpulse/device01/profile" in str(c)
        ]
        self.assertGreaterEqual(len(profile_calls), 1)
        pc = profile_calls[-1]
        kwargs = pc[1] if pc[1] else {}
        self.assertEqual(kwargs.get("qos"), 1)
        self.assertTrue(kwargs.get("retain"))

    def test_valid_pea_config(self):
        self._dispatch("greenpulse/device01/config", '{"plant_type": "Pea"}')
        self.mock_db.save_plant_configuration.assert_called_once()
        crop_arg = self.mock_db.save_plant_configuration.call_args[0][1]
        self.assertEqual(crop_arg["name"], "Pea")

    def test_malformed_json_does_not_crash(self):
        try:
            self._dispatch("greenpulse/device01/config", "not-json{")
        except Exception as exc:
            self.fail(f"Raised on bad JSON: {exc}")
        self.mock_db.save_plant_configuration.assert_not_called()

    def test_empty_payload_does_not_crash(self):
        try:
            self._dispatch("greenpulse/device01/config", "")
        except Exception as exc:
            self.fail(f"Raised on empty payload: {exc}")
        self.mock_db.save_plant_configuration.assert_not_called()

    def test_unsupported_crop_rejected(self):
        self._dispatch("greenpulse/device01/config", '{"plant_type": "DigitalMushroom"}')
        self.mock_db.save_plant_configuration.assert_not_called()

    def test_missing_plant_type_field_rejected(self):
        self._dispatch("greenpulse/device01/config", '{"crop": "Tomato"}')
        self.mock_db.save_plant_configuration.assert_not_called()

    def test_empty_plant_type_rejected(self):
        self._dispatch("greenpulse/device01/config", '{"plant_type": ""}')
        self.mock_db.save_plant_configuration.assert_not_called()


class TestPersistence(unittest.TestCase):

    TEST_DB = "tests/test_mqtt_callback.db"

    def setUp(self):
        if os.path.exists(self.TEST_DB):
            os.remove(self.TEST_DB)
        self.db = Database(self.TEST_DB)
        self.ps = PlantService()

    def tearDown(self):
        try:
            os.remove(self.TEST_DB)
        except Exception:
            pass

    def test_crop_persists_and_restores(self):
        crop = self.ps.parse_and_set_crop('{"plant_type": "Tomato"}')
        self.db.save_plant_configuration("device01", crop)
        restored = self.db.get_latest_plant_configuration("device01")
        self.assertIsNotNone(restored)
        name = restored.get("crop_name") or restored.get("name")
        self.assertEqual(name, "Tomato")

    def test_second_selection_overwrites(self):
        pea = self.ps.parse_and_set_crop('{"plant_type": "Pea"}')
        self.db.save_plant_configuration("device01", pea)
        tomato = self.ps.parse_and_set_crop('{"plant_type": "Tomato"}')
        self.db.save_plant_configuration("device01", tomato)
        restored = self.db.get_latest_plant_configuration("device01")
        name = restored.get("crop_name") or restored.get("name")
        self.assertEqual(name, "Tomato")


class TestProfileContract(unittest.TestCase):

    def test_tomato_profile_valid(self):
        profile = get_profile("Tomato")
        self.assertIsNotNone(profile)
        validated = PlantProfileService.validate_profile(profile)
        self.assertEqual(validated["plant"], "Tomato")

    def test_pea_profile_valid(self):
        profile = get_profile("Pea")
        validated = PlantProfileService.validate_profile(profile)
        self.assertEqual(validated["plant"], "Pea")


class TestReconnectResubscription(unittest.TestCase):

    def test_on_connect_subscribes_four_topics(self):
        svc, mock_client, mock_db = _make_mqtt_service()
        svc._on_connect(
            client=mock_client,
            userdata=None,
            flags=None,
            reason_code=0,
            properties=None,
        )
        subscribed = [c[0][0] for c in mock_client.subscribe.call_args_list]
        self.assertIn("greenpulse/device01/telemetry", subscribed)
        self.assertIn("greenpulse/device01/config", subscribed)
        self.assertIn("greenpulse/device01/location", subscribed)
        self.assertIn("greenpulse/device01/notification/settings", subscribed)


if __name__ == "__main__":
    unittest.main(verbosity=2)

class TestImmediateCareOnPlantChange(unittest.TestCase):
    """
    Verify that switching plant bypasses the 15-minute cooldown and
    immediately triggers a care-intelligence generation when telemetry
    is already available.
    """

    def setUp(self):
        self.svc, self.mock_client, self.mock_db = _make_mqtt_service()

    def _dispatch(self, topic: str, payload: str):
        msg = _make_fake_message(topic, payload)
        self.svc._on_message(client=None, userdata=None, message=msg)

    def test_plant_change_resets_cooldown(self):
        import time as _time
        # Simulate a care generation 30 s ago (within the 15-min cooldown).
        self.svc.last_care_generation_time = _time.monotonic() - 30

        with unittest.mock.patch(
            "greenpulse.mqtt_service.threading.Thread"
        ) as mock_thread:
            mock_thread_instance = unittest.mock.MagicMock()
            mock_thread.return_value = mock_thread_instance

            # Plant change resets cooldown; thread must be spawned despite
            # the 15-min interval not having elapsed.
            self._dispatch(
                "greenpulse/device01/config",
                '{"plant_type": "Tomato"}',
            )

            mock_thread_instance.start.assert_called_once()

    def test_plant_change_uses_latest_telemetry_in_memory(self):
        fake_telemetry = {
            "device_id": "device01",
            "air_temperature": 25.0,
            "humidity": 60.0,
            "soil_moisture": 50,
            "soil_moisture_raw": 2000,
            "light": "BRIGHT",
            "soil_temperature": 22.0,
        }
        self.svc.latest_telemetry = fake_telemetry.copy()
        with unittest.mock.patch(
            "greenpulse.mqtt_service.threading.Thread"
        ) as mock_thread:
            mock_thread_instance = unittest.mock.MagicMock()
            mock_thread.return_value = mock_thread_instance
            self._dispatch("greenpulse/device01/config", '{"plant_type": "Basil"}')
            mock_thread_instance.start.assert_called_once()

    def test_plant_change_falls_back_to_db_telemetry_when_no_cache(self):
        self.svc.latest_telemetry = None
        fake_db_telemetry = {
            "device_id": "device01",
            "air_temperature": 24.0,
            "humidity": 55.0,
            "soil_moisture": 40,
            "soil_moisture_raw": 2200,
            "light": "DARK",
            "soil_temperature": 20.0,
        }
        self.mock_db.get_latest_telemetry.return_value = fake_db_telemetry
        self._dispatch("greenpulse/device01/config", '{"plant_type": "Mint"}')
        self.mock_db.get_latest_telemetry.assert_called_once_with("device01")

    def test_plant_change_without_any_telemetry_does_not_crash(self):
        self.svc.latest_telemetry = None
        self.mock_db.get_latest_telemetry.return_value = None
        try:
            self._dispatch("greenpulse/device01/config", '{"plant_type": "Lettuce"}')
        except Exception as exc:
            self.fail(f"Plant change without any telemetry raised: {exc}")
