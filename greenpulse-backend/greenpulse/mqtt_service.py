"""
GreenPulse - MQTT Service

Handles communication between:

ESP32
    ↓
HiveMQ Cloud
    ↓
GreenPulse Python Backend
    ↓
SQLite / Weather / Email / Gemini
    ↓
HiveMQ Cloud
    ↓
ESP32 + Node-RED

Plant threshold profiles are deterministic and loaded from
crop_catalog.py.

Gemini is used ONLY for Care Intelligence.
"""

import json
import logging
import ssl
import threading
import time

from datetime import datetime, timezone

import paho.mqtt.client as mqtt

from greenpulse.care_service import (
    CareService,
    CareServiceError,
)

from greenpulse.config import Config

from greenpulse.crop_catalog import get_profile

from greenpulse.database import Database

from greenpulse.gemini_service import GeminiService

from greenpulse.location_service import (
    LocationService,
    LocationValidationError,
)

from greenpulse.plant_profile_service import (
    PlantProfileService,
    PlantProfileValidationError,
)

from greenpulse.plant_service import (
    PlantService,
    PlantConfigError,
)

from greenpulse.telemetry_service import (
    TelemetryService,
    TelemetryValidationError,
)

from datetime import datetime, timezone
from greenpulse.notification_service import NotificationService
from greenpulse.daily_summary_service import DailySummaryService


# ============================================================
# MQTT TOPICS
# ============================================================

TELEMETRY_TOPIC = "greenpulse/device01/telemetry"
CONFIG_TOPIC = "greenpulse/device01/config"
LOCATION_TOPIC = "greenpulse/device01/location"
PROFILE_TOPIC = "greenpulse/device01/profile"
AI_TOPIC = "greenpulse/device01/ai"

# Extended Topics for Worldwide Location & Notifications
LOCATION_RESOLVED_TOPIC = "greenpulse/device01/location/resolved"
NOTIFICATION_SETTINGS_TOPIC = "greenpulse/device01/notification/settings"
NOTIFICATION_SETTINGS_STATE_TOPIC = "greenpulse/device01/notification/settings/state"
NOTIFICATIONS_TOPIC = "greenpulse/device01/notifications"
NOTIFICATION_STATUS_TOPIC = "greenpulse/device01/notification/status"

DEVICE_ID = "device01"


# ============================================================
# CARE INTELLIGENCE SETTINGS
# ============================================================

# Gemini/weather/email should NOT run for every
# telemetry packet.
CARE_GENERATION_INTERVAL_SECONDS = 15 * 60


# ============================================================
# LOGGER
# ============================================================

logger = logging.getLogger("greenpulse.mqtt")


# ============================================================
# MQTT SERVICE
# ============================================================

class MQTTService:
    """
    Handles MQTT communication for GreenPulse.

    Plant profiles:
        Local deterministic crop catalog.

    Care Intelligence:
        Gemini + telemetry + profile + weather +
        relevant notification/email context.
    """

    def __init__(self):
        """Initialize GreenPulse MQTT services."""

        # -------------------------------------------------
        # Configuration
        # -------------------------------------------------

        Config.validate()

        # -------------------------------------------------
        # Database
        # -------------------------------------------------

        self.database = Database()

        # -------------------------------------------------
        # Plant configuration
        # -------------------------------------------------

        self.plant_service = PlantService()

        # -------------------------------------------------
        # Gemini
        #
        # IMPORTANT:
        # Gemini is used for Care Intelligence only.
        # It no longer generates plant thresholds.
        # -------------------------------------------------

        self.gemini_service = GeminiService()

        # -------------------------------------------------
        # Care Intelligence
        # -------------------------------------------------

        self.care_service = CareService()

        # -------------------------------------------------
        # Care worker protection
        # -------------------------------------------------

        self.care_generation_lock = threading.Lock()

        # Monotonic clock is used for cooldown timing.
        self.last_care_generation_time = 0.0

        # -------------------------------------------------
        # Restore plant configuration
        # -------------------------------------------------

        self._restore_plant_configuration()

        # -------------------------------------------------
        # MQTT client
        # -------------------------------------------------

        self.client = mqtt.Client(
            callback_api_version=(
                mqtt.CallbackAPIVersion.VERSION2
            ),
            client_id="greenpulse_backend",
        )

        # -------------------------------------------------
        # Authentication
        # -------------------------------------------------

        self.client.username_pw_set(
            Config.MQTT_USERNAME,
            Config.MQTT_PASSWORD,
        )

        # -------------------------------------------------
        # TLS
        # -------------------------------------------------

        self.client.tls_set(
            cert_reqs=ssl.CERT_REQUIRED,
            tls_version=ssl.PROTOCOL_TLS_CLIENT,
        )

        # -------------------------------------------------
        # MQTT callbacks
        # -------------------------------------------------

        self.client.on_connect = self._on_connect

        self.client.on_message = self._on_message

        self.client.on_subscribe = self._on_subscribe

        self.client.on_disconnect = self._on_disconnect

        # -------------------------------------------------
        # Notification & Daily Summary Engines
        # -------------------------------------------------
        self.notification_service = NotificationService(
            database=self.database,
            gemini_service=self.gemini_service,
        )
        self.notification_service.set_mqtt_publish_callback(
            lambda topic, payload, qos=1, retain=False: self.client.publish(
                topic, payload, qos=qos, retain=retain
            )
        )

        self.daily_summary_service = DailySummaryService(
            database=self.database,
            gemini_service=self.gemini_service,
            weather_service=self.care_service.weather_service,
        )
        try:
            self.daily_summary_service.start()
        except Exception as err:
            logger.warning("Could not start daily summary scheduler: %s", err)

    # =====================================================
    # RESTORE PLANT CONFIGURATION
    # =====================================================

    def _restore_plant_configuration(self):
        """Restore latest selected crop from SQLite."""

        stored_crop = (
            self.database
            .get_latest_plant_configuration(
                DEVICE_ID
            )
        )

        if stored_crop is None:

            logger.info(
                "No previous plant configuration found."
            )

            return

        self.plant_service.current_crop_name = (
            stored_crop["crop_name"]
        )

        logger.info(
            "Restored plant configuration. "
            "Crop=%s Category=%s",
            stored_crop["name"],
            stored_crop["category"],
        )

    # =====================================================
    # MQTT CONNECT CALLBACK
    # =====================================================

    def _on_connect(
        self,
        client,
        userdata,
        flags,
        reason_code,
        properties,
    ):
        """Called when backend connects to HiveMQ."""

        if reason_code != 0:

            logger.error(
                "MQTT connection failed. Reason=%s",
                reason_code,
            )

            return

        logger.info(
            "Connected to MQTT broker %s:%s",
            Config.MQTT_HOST,
            Config.MQTT_PORT,
        )

        self._subscribe(
            TELEMETRY_TOPIC,
            qos=0,
        )

        self._subscribe(
            CONFIG_TOPIC,
            qos=0,
        )

        self._subscribe(
            LOCATION_TOPIC,
            qos=0,
        )

        self._subscribe(
            NOTIFICATION_SETTINGS_TOPIC,
            qos=1,
        )

        # Republish stored profiles, resolved location, and notification
        # settings state so ESP32 and Node-RED synchronize upon connecting.
        self._publish_latest_stored_profile()
        self._publish_latest_stored_location()
        self._publish_notification_state()

    # =====================================================
    # SUBSCRIBE HELPER
    # =====================================================

    def _subscribe(
        self,
        topic: str,
        qos: int = 0,
    ):
        """Subscribe to an MQTT topic."""

        result, message_id = self.client.subscribe(
            topic,
            qos=qos,
        )

        if result == mqtt.MQTT_ERR_SUCCESS:

            logger.info(
                "Subscription request sent. "
                "Topic=%s MessageID=%s",
                topic,
                message_id,
            )

        else:

            logger.error(
                "Failed to subscribe. "
                "Topic=%s Error=%s",
                topic,
                result,
            )

    # =====================================================
    # SUBSCRIBE CALLBACK
    # =====================================================

    def _on_subscribe(
        self,
        client,
        userdata,
        mid,
        reason_code_list,
        properties,
    ):
        """Called when HiveMQ confirms subscription."""

        logger.info(
            "MQTT subscription confirmed. "
            "MessageID=%s Result=%s",
            mid,
            reason_code_list,
        )

    # =====================================================
    # MESSAGE CALLBACK
    # =====================================================

    def _on_message(
        self,
        client,
        userdata,
        message,
    ):
        """
        Route incoming MQTT messages.

        Long-running Gemini/weather/email operations
        never execute directly in this callback.
        """

        try:

            payload = message.payload.decode(
                "utf-8"
            )

        except UnicodeDecodeError:

            logger.warning(
                "MQTT message rejected: "
                "invalid UTF-8. Topic=%s",
                message.topic,
            )

            return

        logger.info(
            "MQTT message received. Topic=%s",
            message.topic,
        )

        if message.topic == TELEMETRY_TOPIC:

            self._handle_telemetry(
                payload
            )

        elif message.topic == CONFIG_TOPIC:

            self._handle_plant_configuration(
                payload
            )

        elif message.topic == LOCATION_TOPIC:

            self._handle_location(
                payload
            )

        elif message.topic == NOTIFICATION_SETTINGS_TOPIC:

            self._handle_notification_settings(
                payload
            )

        else:

            logger.warning(
                "Message received from "
                "unexpected topic: %s",
                message.topic,
            )

    # =====================================================
    # TELEMETRY HANDLER
    # =====================================================

    def _handle_telemetry(
        self,
        payload: str,
    ):
        """
        Validate and store telemetry.

        Valid telemetry may trigger Care Intelligence
        in a separate background thread.
        """

        try:

            telemetry = (
                TelemetryService
                .parse_and_validate(
                    payload
                )
            )

            logger.info(
                "Telemetry validation passed. "
                "Device=%s",
                telemetry["device_id"],
            )

            # ---------------------------------------------
            # Device check
            # ---------------------------------------------

            if telemetry["device_id"] != DEVICE_ID:

                logger.warning(
                    "Telemetry rejected. "
                    "Unexpected Device=%s Expected=%s",
                    telemetry["device_id"],
                    DEVICE_ID,
                )

                return

            # ---------------------------------------------
            # Store telemetry
            # ---------------------------------------------

            record_id = (
                self.database.save_telemetry(
                    telemetry
                )
            )

            logger.info(
                "Telemetry stored successfully. "
                "RecordID=%s Device=%s "
                "AirTemperature=%s Humidity=%s "
                "SoilMoisture=%s "
                "SoilMoistureRaw=%s "
                "Light=%s "
                "SoilTemperature=%s",
                record_id,
                telemetry["device_id"],
                telemetry["air_temperature"],
                telemetry["humidity"],
                telemetry["soil_moisture"],
                telemetry["soil_moisture_raw"],
                telemetry["light"],
                telemetry["soil_temperature"],
            )

            self._request_care_generation(
                telemetry
            )

            # ---------------------------------------------
            # Automated Condition Notifications
            # ---------------------------------------------
            self._evaluate_notifications(
                telemetry
            )

        except TelemetryValidationError as error:

            logger.warning(
                "Telemetry validation failed. "
                "Reason=%s",
                error,
            )

        except Exception:

            logger.exception(
                "Unexpected error while "
                "processing telemetry."
            )

    # =====================================================
    # CARE GENERATION TRIGGER
    # =====================================================

    def _request_care_generation(
        self,
        telemetry: dict,
    ):
        """
        Start Care Intelligence when the cooldown
        interval allows it.

        The MQTT callback never waits for Gemini,
        weather, or Gmail.
        """

        current_time = time.monotonic()

        elapsed = (
            current_time
            - self.last_care_generation_time
        )

        if (
            self.last_care_generation_time > 0
            and elapsed
            < CARE_GENERATION_INTERVAL_SECONDS
        ):

            remaining = int(
                CARE_GENERATION_INTERVAL_SECONDS
                - elapsed
            )

            logger.debug(
                "Care generation skipped due "
                "to cooldown. Remaining=%ss",
                remaining,
            )

            return

        # Avoid creating another worker if one is
        # already processing a care request.

        if self.care_generation_lock.locked():

            logger.info(
                "Care generation already in progress. "
                "Current telemetry stored normally."
            )

            return

        worker = threading.Thread(
            target=self._generate_care_worker,
            args=(telemetry.copy(),),
            daemon=True,
            name="greenpulse-care-worker",
        )

        worker.start()

        logger.info(
            "Care Intelligence generation started "
            "in background."
        )

    # =====================================================
    # CARE INTELLIGENCE WORKER
    # =====================================================

    def _generate_care_worker(
        self,
        telemetry: dict,
    ):
        """
        Build real GreenPulse context, request Gemini
        intelligence, and publish a validated AI result.

        Failures never stop MQTT telemetry processing.
        """

        acquired = (
            self.care_generation_lock.acquire(
                blocking=False
            )
        )

        if not acquired:
            return

        try:

            # ---------------------------------------------
            # Mark attempt time
            # ---------------------------------------------

            self.last_care_generation_time = (
                time.monotonic()
            )

            # ---------------------------------------------
            # Build real context
            # ---------------------------------------------

            logger.info(
                "Building Care Intelligence context."
            )

            context = (
                self.care_service.build_context(
                    telemetry
                )
            )

            logger.info(
                "Care Intelligence context built. "
                "Plant=%s WeatherAvailable=%s "
                "RelevantEmails=%s",
                context["plant"],
                context["weather"] is not None,
                len(
                    context["relevant_emails"]
                ),
            )

            # ---------------------------------------------
            # Gemini Care Intelligence
            # ---------------------------------------------

            logger.info(
                "Requesting Gemini Care Intelligence. "
                "Plant=%s",
                context["plant"],
            )

            care_response = (
                self.gemini_service
                .generate_care_response(
                    context
                )
            )

            # ---------------------------------------------
            # Final MQTT payload
            # ---------------------------------------------

            ai_result = {
                "device_id": DEVICE_ID,

                "plant": context["plant"],

                "priority": (
                    care_response["priority"]
                ),

                "care_quote": (
                    care_response["care_quote"]
                ),

                "condition_summary": (
                    care_response[
                        "condition_summary"
                    ]
                ),

                "care_tip": (
                    care_response["care_tip"]
                ),

                "weather_summary": (
                    care_response[
                        "weather_summary"
                    ]
                ),

                "alert_summary": (
                    care_response[
                        "alert_summary"
                    ]
                ),

                "generated_at": (
                    datetime.now(
                        timezone.utc
                    ).isoformat()
                ),
            }

            logger.info(
                "Gemini Care Intelligence "
                "generated successfully. "
                "Plant=%s Priority=%s",
                ai_result["plant"],
                ai_result["priority"],
            )

            # ---------------------------------------------
            # Publish
            # ---------------------------------------------

            self._publish_ai_result(
                ai_result
            )

        except CareServiceError as error:

            logger.warning(
                "Care Intelligence context "
                "could not be built. Reason=%s",
                error,
            )

        except Exception as error:

            logger.error(
                "Care Intelligence generation failed. "
                "Reason=%s",
                error,
            )

            logger.warning(
                "MQTT telemetry processing will "
                "continue. No replacement AI message "
                "will be published."
            )

        finally:

            self.care_generation_lock.release()

    # =====================================================
    # PUBLISH AI RESULT
    # =====================================================

    def _publish_ai_result(
        self,
        ai_result: dict,
    ):
        """
        Publish latest validated AI result.

        QoS 1:
            Broker acknowledgement.

        Retained:
            ESP32 and Node-RED can receive the latest
            valid result after reconnecting.
        """

        payload = json.dumps(
            ai_result,
            ensure_ascii=False,
        )

        message_info = self.client.publish(
            topic=AI_TOPIC,
            payload=payload,
            qos=1,
            retain=True,
        )

        if (
            message_info.rc
            == mqtt.MQTT_ERR_SUCCESS
        ):

            logger.info(
                "AI result publish queued. "
                "Topic=%s Plant=%s "
                "Priority=%s QoS=1 "
                "Retain=True MessageID=%s",
                AI_TOPIC,
                ai_result["plant"],
                ai_result["priority"],
                message_info.mid,
            )

        else:

            logger.error(
                "Failed to publish AI result. "
                "Topic=%s Error=%s",
                AI_TOPIC,
                message_info.rc,
            )

    # =====================================================
    # LOCATION HANDLER
    # =====================================================

    def _handle_location(
        self,
        payload: str,
    ):
        """Validate and store greenhouse location."""

        try:

            location = (
                LocationService
                .parse_and_validate(
                    payload
                )
            )

            logger.info(
                "Location validation passed. "
                "Device=%s Latitude=%s Longitude=%s",
                location["device_id"],
                location["latitude"],
                location["longitude"],
            )

            if location["device_id"] != DEVICE_ID:

                logger.warning(
                    "Location rejected. "
                    "Unexpected Device=%s Expected=%s",
                    location["device_id"],
                    DEVICE_ID,
                )

                return

            record_id = (
                self.database
                .save_device_location(
                    location
                )
            )

            logger.info(
                "Greenhouse location stored "
                "successfully. RecordID=%s "
                "Device=%s Latitude=%s Longitude=%s",
                record_id,
                location["device_id"],
                location["latitude"],
                location["longitude"],
            )

            # Publish resolved location confirmation (retained)
            self._publish_location_resolved(location)

        except LocationValidationError as error:

            logger.warning(
                "Location validation failed. "
                "Reason=%s",
                error,
            )

        except Exception:

            logger.exception(
                "Unexpected error while processing "
                "greenhouse location."
            )

    # =====================================================
    # PLANT CONFIGURATION HANDLER
    # =====================================================

    def _handle_plant_configuration(
        self,
        payload: str,
    ):
        """
        Validate and store selected plant.

        The matching plant profile is loaded immediately
        from the local deterministic crop catalog.

        Gemini is NOT used for plant thresholds.
        """

        try:

            # ---------------------------------------------
            # Validate selected crop
            # ---------------------------------------------

            crop = (
                self.plant_service
                .parse_and_set_crop(
                    payload
                )
            )

            logger.info(
                "Plant selection validated. "
                "Crop=%s Category=%s",
                crop["name"],
                crop["category"],
            )

            # ---------------------------------------------
            # Store selected crop
            # ---------------------------------------------

            record_id = (
                self.database
                .save_plant_configuration(
                    DEVICE_ID,
                    crop,
                )
            )

            logger.info(
                "Plant configuration stored. "
                "RecordID=%s Crop=%s Category=%s",
                record_id,
                crop["name"],
                crop["category"],
            )

            # ---------------------------------------------
            # Get deterministic profile
            # ---------------------------------------------

            profile = get_profile(
                crop["name"]
            )

            if profile is None:

                raise PlantProfileValidationError(
                    "No local plant profile found "
                    f"for crop: {crop['name']}"
                )

            # ---------------------------------------------
            # Validate local profile
            # ---------------------------------------------

            profile = (
                PlantProfileService
                .validate_profile(
                    profile
                )
            )

            logger.info(
                "Local plant profile loaded and "
                "validated. Crop=%s",
                profile["plant"],
            )

            # ---------------------------------------------
            # Store profile
            # ---------------------------------------------

            profile_record_id = (
                self.database
                .save_plant_profile(
                    DEVICE_ID,
                    profile,
                )
            )

            logger.info(
                "Plant profile stored successfully. "
                "RecordID=%s Crop=%s",
                profile_record_id,
                profile["plant"],
            )

            # ---------------------------------------------
            # Publish profile immediately
            # ---------------------------------------------

            self._publish_plant_profile(
                profile
            )

            logger.info(
                "Plant configuration completed using "
                "local crop catalog. Crop=%s",
                profile["plant"],
            )

        except PlantConfigError as error:

            logger.warning(
                "Plant configuration rejected. "
                "Reason=%s",
                error,
            )

        except PlantProfileValidationError as error:

            logger.warning(
                "Plant profile rejected. "
                "Reason=%s",
                error,
            )

        except Exception:

            logger.exception(
                "Unexpected error while processing "
                "plant configuration."
            )

    # =====================================================
    # PUBLISH PLANT PROFILE
    # =====================================================

    def _publish_plant_profile(
        self,
        profile: dict,
    ):
        """
        Publish validated deterministic plant profile.

        QoS 1:
            Broker acknowledgement.

        Retained:
            ESP32 and Node-RED receive the latest profile
            when they reconnect.
        """

        payload = json.dumps(
            profile,
            ensure_ascii=False,
        )

        message_info = self.client.publish(
            topic=PROFILE_TOPIC,
            payload=payload,
            qos=1,
            retain=True,
        )

        if (
            message_info.rc
            == mqtt.MQTT_ERR_SUCCESS
        ):

            logger.info(
                "Plant profile publish queued. "
                "Topic=%s Crop=%s QoS=1 "
                "Retain=True MessageID=%s",
                PROFILE_TOPIC,
                profile["plant"],
                message_info.mid,
            )

        else:

            logger.error(
                "Failed to publish plant profile. "
                "Topic=%s Error=%s",
                PROFILE_TOPIC,
                message_info.rc,
            )

    # =====================================================
    # RESTORE STORED PROFILE
    # =====================================================

    def _publish_latest_stored_profile(self):
        """
        Republish latest valid stored profile.

        This allows ESP32 and Node-RED to recover the
        latest profile when the backend reconnects.
        """

        try:

            profile = (
                self.database
                .get_latest_plant_profile(
                    DEVICE_ID
                )
            )

            if profile is None:

                logger.info(
                    "No stored plant profile found."
                )

                return

            # Database metadata is not part of the MQTT
            # profile contract.
            profile.pop(
                "created_at",
                None,
            )

            # Validate before publishing old stored data.
            profile = (
                PlantProfileService
                .validate_profile(
                    profile
                )
            )

            logger.info(
                "Restoring stored plant profile. "
                "Crop=%s",
                profile["plant"],
            )

            self._publish_plant_profile(
                profile
            )

        except PlantProfileValidationError as error:

            logger.warning(
                "Stored plant profile is invalid "
                "and will not be published. "
                "Reason=%s",
                error,
            )

        except Exception:

            logger.exception(
                "Failed to restore stored "
                "plant profile."
            )

    # =====================================================
    # DISCONNECT CALLBACK
    # =====================================================

    def _on_disconnect(
        self,
        client,
        userdata,
        disconnect_flags,
        reason_code,
        properties,
    ):
        """Called when MQTT connection closes."""

        if reason_code == 0:

            logger.info(
                "MQTT client disconnected normally."
            )

        else:

            logger.warning(
                "MQTT client disconnected "
                "unexpectedly. Reason=%s",
                reason_code,
            )

    # =====================================================
    # LOCATION RESOLUTION & RESTORATION
    # =====================================================

    def _publish_location_resolved(self, location: dict):
        """Publish confirmed/resolved location details to MQTT (retained)."""
        try:
            display_name = LocationService.format_display_name(location)
            resolved_payload = {
                "device_id": location.get("device_id", DEVICE_ID),
                "location_name": display_name,
                "admin1": location.get("admin1"),
                "country": location.get("country"),
                "country_code": location.get("country_code"),
                "geocoding_id": location.get("geocoding_id"),
                "latitude": location.get("latitude"),
                "longitude": location.get("longitude"),
                "resolved_at": datetime.now(timezone.utc).isoformat(),
            }
            self.client.publish(
                LOCATION_RESOLVED_TOPIC,
                json.dumps(resolved_payload, ensure_ascii=False),
                qos=1,
                retain=True,
            )
            logger.info("Published resolved location: %s", display_name)
        except Exception:
            logger.exception("Failed to publish resolved location.")

    def _publish_latest_stored_location(self):
        """Restore latest valid location on connect."""
        try:
            loc = self.database.get_latest_device_location(DEVICE_ID)
            if loc:
                logger.info("Restoring stored location on connect: %s", loc.get("location_name"))
                self._publish_location_resolved(loc)
        except Exception:
            logger.exception("Failed to restore stored location.")

    # =====================================================
    # AUTOMATED CONDITION EVALUATION
    # =====================================================

    def _evaluate_notifications(self, telemetry: dict):
        """Evaluate telemetry conditions against plant thresholds in background."""
        try:
            plant_cfg = self.database.get_latest_plant_configuration(DEVICE_ID)
            profile = self.database.get_latest_plant_profile(DEVICE_ID)
            if not profile:
                return

            plant_name = (
                plant_cfg.get("name") or plant_cfg.get("crop_name")
                if plant_cfg else profile.get("plant", "Greenhouse Crop")
            )
            location = self.database.get_latest_device_location(DEVICE_ID)

            weather = None
            if location and location.get("latitude") and location.get("longitude"):
                try:
                    weather = self.care_service.weather_service.get_weather(
                        location["latitude"], location["longitude"]
                    )
                except Exception:
                    pass

            self.notification_service.evaluate_telemetry(
                telemetry=telemetry,
                plant_name=plant_name,
                profile=profile,
                location=location,
                weather=weather,
            )
        except Exception:
            logger.exception("Error during automated notification evaluation.")

    # =====================================================
    # NOTIFICATION SETTINGS & RECIPIENT HANDLER
    # =====================================================

    def _handle_notification_settings(self, payload: str):
        """
        Handle recipient management and test-email commands from Node-RED.
        Supported actions:
        - GET_STATE
        - ADD_RECIPIENT: {"action": "ADD_RECIPIENT", "email": "...", "preferences": {...}}
        - UPDATE_RECIPIENT: {"action": "UPDATE_RECIPIENT", "email": "...", "preferences": {...}}
        - REMOVE_RECIPIENT: {"action": "REMOVE_RECIPIENT", "email": "..."}
        - SEND_TEST_EMAIL: {"action": "SEND_TEST_EMAIL", "email": "..."}
        """
        try:
            data = json.loads(payload)
            if not isinstance(data, dict):
                return

            action = data.get("action", "GET_STATE").upper()
            email = data.get("email")

            if action == "ADD_RECIPIENT" and email:
                prefs = data.get("preferences") or {}
                try:
                    self.notification_service.add_recipient(email, prefs)
                    logger.info("Recipient added: %s", email)
                except Exception as err:
                    logger.warning("Failed to add recipient %s: %s", email, err)

            elif action == "UPDATE_RECIPIENT" and email:
                prefs = data.get("preferences") or {}
                self.notification_service.update_recipient(email, prefs)
                logger.info("Recipient updated: %s", email)

            elif action == "REMOVE_RECIPIENT" and email:
                self.notification_service.remove_recipient(email)
                logger.info("Recipient removed: %s", email)

            elif action == "SEND_TEST_EMAIL" and email:
                test_res = self.notification_service.send_test_email(email)
                logger.info("Test email result for %s: %s", email, test_res.get("status"))

            # Publish updated state snapshot
            self._publish_notification_state()

        except Exception:
            logger.exception("Error handling notification settings message.")

    def _publish_notification_state(self):
        """Publish full notification recipients & recent history state (retained)."""
        try:
            recipients = self.notification_service.get_recipients()
            history = self.notification_service.get_recent_notifications(limit=10)
            state_payload = {
                "device_id": DEVICE_ID,
                "recipients": recipients,
                "recent_notifications": history,
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }
            self.client.publish(
                NOTIFICATION_SETTINGS_STATE_TOPIC,
                json.dumps(state_payload, ensure_ascii=False),
                qos=1,
                retain=True,
            )
            logger.debug("Published notification settings state (%d recipients).", len(recipients))
        except Exception:
            logger.exception("Failed to publish notification state.")

    # =====================================================
    # CONNECT
    # =====================================================

    def connect(self):
        """Connect to HiveMQ and process messages."""

        logger.info(
            "Connecting to MQTT broker..."
        )

        self.client.connect(
            Config.MQTT_HOST,
            Config.MQTT_PORT,
            keepalive=60,
        )

        self.client.loop_forever()
