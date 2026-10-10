"""
GreenPulse - Notification Service

Evaluates live greenhouse telemetry against active plant profiles,
detects conditions (Watering, High/Low Temp, Humidity, Weather risks),
manages alert state machines with persistence and cooldowns,
invokes Gemini AI for contextual titles/summaries/tips (with deterministic fallback),
queues asynchronous email delivery to subscribed recipients via SmtpSender,
and publishes notification updates over MQTT.
"""
from datetime import datetime, timezone, timedelta
import logging
import queue
import threading
from typing import Dict, Any, List, Optional, Callable

from greenpulse.database import Database
from greenpulse.email_service import SmtpSender
from greenpulse.gemini_service import GeminiService
from greenpulse.location_service import LocationService

logger = logging.getLogger("greenpulse.notifications")

DEVICE_ID = "device01"


class NotificationService:
    """Core alert detection, state management, and delivery engine."""

    # Configurable cooldowns in minutes to prevent notification fatigue
    DEFAULT_COOLDOWNS = {
        "WATERING": 120,          # 2 hours between watering alerts
        "TEMPERATURE_HIGH": 60,   # 1 hour
        "TEMPERATURE_LOW": 60,    # 1 hour
        "HUMIDITY": 60,           # 1 hour
        "WEATHER": 180,           # 3 hours
        "SYSTEM": 60,             # 1 hour
    }

    REQUIRED_CONSECUTIVE_ALERTS = 2     # Need 2 bad samples to trigger (filters sensor noise)
    REQUIRED_CONSECUTIVE_RECOVERIES = 2  # Need 2 good samples to declare recovery
    TEST_EMAIL_RATE_LIMIT_SECONDS = 300 # Max 1 test email per recipient per 5 mins

    def __init__(
        self,
        database: Optional[Database] = None,
        smtp_sender: Optional[SmtpSender] = None,
        gemini_service: Optional[GeminiService] = None,
        cooldowns: Optional[Dict[str, int]] = None,
    ):
        self.database = database or Database()
        self.smtp_sender = smtp_sender or SmtpSender()
        self.gemini_service = gemini_service
        self.cooldowns = cooldowns or dict(self.DEFAULT_COOLDOWNS)

        self._mqtt_publish_callback: Optional[Callable[[str, str, int, bool], None]] = None

        # Asynchronous email delivery queue and worker thread
        self._email_queue: queue.Queue = queue.Queue()
        self._worker_running = True
        self._worker_thread = threading.Thread(
            target=self._email_worker_loop,
            daemon=True,
            name="GreenPulse-EmailWorker"
        )
        self._worker_thread.start()

        # In-memory tracking of transient recovery counts: {(device_id, alert_type): count}
        self._recovery_counts: Dict[tuple, int] = {}

    def set_mqtt_publish_callback(self, callback: Callable[[str, str, int, bool], None]):
        """Register a callback: func(topic, payload_str, qos, retain) to publish MQTT messages."""
        self._mqtt_publish_callback = callback

    def _get_gemini(self) -> Optional[GeminiService]:
        """Lazy-load GeminiService if available."""
        if self.gemini_service is None:
            try:
                self.gemini_service = GeminiService()
            except Exception as err:
                logger.debug("GeminiService not available for notifications: %s", err)
        return self.gemini_service

    # =========================================================================
    # TELEMETRY EVALUATION & CONDITION DETECTION
    # =========================================================================

    def evaluate_telemetry(
        self,
        telemetry: Dict[str, Any],
        plant_name: str,
        profile: Dict[str, Any],
        location: Optional[Dict[str, Any]] = None,
        weather: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        """
        Evaluate current telemetry against plant profile thresholds.
        Detects transitions into alerts or back to normal (recovery).

        Returns list of newly generated notifications (if any).
        """
        if not telemetry or not profile:
            return []

        device_id = telemetry.get("device_id", DEVICE_ID)
        now = datetime.now(timezone.utc)
        generated_notifications = []

        # Condition checks mapping
        condition_checks = self._check_profile_conditions(telemetry, profile)

        for alert_type, check_data in condition_checks.items():
            is_active = check_data["is_violated"]
            priority = check_data["priority"]
            category = check_data["category"]

            # Read persisted alert state for restart safety
            stored_state = self.database.get_alert_state(device_id, alert_type)
            current_state = stored_state.get("state", "NORMAL")
            consecutive = stored_state.get("consecutive_count", 0)
            cooldown_until_str = stored_state.get("cooldown_until")

            is_cooldown_expired = True
            if cooldown_until_str:
                try:
                    cd_dt = datetime.fromisoformat(cooldown_until_str)
                    if cd_dt.tzinfo is None:
                        cd_dt = cd_dt.replace(tzinfo=timezone.utc)
                    if now < cd_dt:
                        is_cooldown_expired = False
                except Exception:
                    is_cooldown_expired = True

            rec_key = (device_id, alert_type)

            if is_active:
                # Reset recovery streak since condition is currently violated
                self._recovery_counts[rec_key] = 0
                new_consecutive = consecutive + 1

                # Condition violated: check if we should trigger an alert
                should_trigger = False
                if current_state != "ALERT" and new_consecutive >= self.REQUIRED_CONSECUTIVE_ALERTS:
                    should_trigger = True
                elif current_state == "ALERT" and is_cooldown_expired:
                    should_trigger = True

                if should_trigger:
                    cooldown_mins = self.cooldowns.get(alert_type, 60)
                    next_cooldown = (now + timedelta(minutes=cooldown_mins)).isoformat()

                    self.database.save_alert_state(device_id, alert_type, {
                        "state": "ALERT",
                        "consecutive_count": new_consecutive,
                        "last_triggered_at": now.isoformat(),
                        "cooldown_until": next_cooldown,
                        "alert_started_at": stored_state.get("alert_started_at") or now.isoformat(),
                    })

                    notif = self._generate_and_dispatch_notification(
                        device_id=device_id,
                        alert_type=alert_type,
                        priority=priority,
                        category=category,
                        plant=plant_name,
                        telemetry=telemetry,
                        profile=profile,
                        location=location,
                        weather=weather,
                        is_recovery=False,
                    )
                    if notif:
                        generated_notifications.append(notif)
                else:
                    # Update consecutive count in state
                    self.database.save_alert_state(device_id, alert_type, {
                        "state": current_state,
                        "consecutive_count": new_consecutive,
                        "last_triggered_at": stored_state.get("last_triggered_at"),
                        "cooldown_until": cooldown_until_str,
                        "alert_started_at": stored_state.get("alert_started_at"),
                    })

            else:
                # Condition is currently within normal thresholds
                if current_state == "ALERT":
                    current_rec = self._recovery_counts.get(rec_key, 0) + 1
                    self._recovery_counts[rec_key] = current_rec

                    if current_rec >= self.REQUIRED_CONSECUTIVE_RECOVERIES:
                        # State transition: ALERT -> NORMAL (Recovery)
                        self.database.save_alert_state(device_id, alert_type, {
                            "state": "NORMAL",
                            "consecutive_count": 0,
                            "last_triggered_at": None,
                            "cooldown_until": None,
                            "alert_started_at": None,
                        })
                        self._recovery_counts[rec_key] = 0

                        rec_notif = self._generate_and_dispatch_notification(
                            device_id=device_id,
                            alert_type=alert_type,
                            priority="INFO",
                            category="RECOVERY",
                            plant=plant_name,
                            telemetry=telemetry,
                            profile=profile,
                            location=location,
                            weather=weather,
                            is_recovery=True,
                        )
                        if rec_notif:
                            generated_notifications.append(rec_notif)
                else:
                    # Normal state maintained
                    if consecutive > 0:
                        self.database.save_alert_state(device_id, alert_type, {
                            "state": "NORMAL",
                            "consecutive_count": 0,
                            "last_triggered_at": stored_state.get("last_triggered_at"),
                            "cooldown_until": None,
                            "alert_started_at": None,
                        })

        return generated_notifications

    def _check_profile_conditions(
        self,
        telemetry: Dict[str, Any],
        profile: Dict[str, Any]
    ) -> Dict[str, Dict[str, Any]]:
        """Evaluates sensor readings against plant profile limits."""
        checks = {}

        # 1. Soil Moisture / Watering
        soil_m = telemetry.get("soil_moisture")
        sm_profile = profile.get("soil_moisture", {})
        if soil_m is not None and isinstance(sm_profile, dict) and "min" in sm_profile:
            min_val = float(sm_profile["min"])
            curr_val = float(soil_m)
            if curr_val < min_val:
                is_crit = curr_val < max(0.0, min_val - 15.0)
                checks["WATERING"] = {
                    "is_violated": True,
                    "priority": "CRITICAL" if is_crit else "MEDIUM",
                    "category": "WATERING",
                }
            else:
                checks["WATERING"] = {"is_violated": False, "priority": "LOW", "category": "WATERING"}

        # 2. Air Temperature
        air_t = telemetry.get("air_temperature")
        at_profile = profile.get("air_temperature", {})
        if air_t is not None and isinstance(at_profile, dict):
            min_t = at_profile.get("min")
            max_t = at_profile.get("max")
            curr_t = float(air_t)

            if max_t is not None and curr_t > float(max_t):
                is_crit = curr_t > (float(max_t) + 5.0)
                checks["TEMPERATURE_HIGH"] = {
                    "is_violated": True,
                    "priority": "CRITICAL" if is_crit else "HIGH",
                    "category": "TEMPERATURE",
                }
            else:
                checks["TEMPERATURE_HIGH"] = {"is_violated": False, "priority": "LOW", "category": "TEMPERATURE"}

            if min_t is not None and curr_t < float(min_t):
                is_crit = curr_t < (float(min_t) - 5.0)
                checks["TEMPERATURE_LOW"] = {
                    "is_violated": True,
                    "priority": "CRITICAL" if is_crit else "HIGH",
                    "category": "TEMPERATURE",
                }
            else:
                checks["TEMPERATURE_LOW"] = {"is_violated": False, "priority": "LOW", "category": "TEMPERATURE"}

        # 3. Humidity
        hum = telemetry.get("humidity")
        hum_profile = profile.get("humidity", {})
        if hum is not None and isinstance(hum_profile, dict):
            min_h = hum_profile.get("min")
            max_h = hum_profile.get("max")
            curr_h = float(hum)
            if (min_h is not None and curr_h < float(min_h)) or (max_h is not None and curr_h > float(max_h)):
                checks["HUMIDITY"] = {
                    "is_violated": True,
                    "priority": "MEDIUM",
                    "category": "HUMIDITY",
                }
            else:
                checks["HUMIDITY"] = {"is_violated": False, "priority": "LOW", "category": "HUMIDITY"}

        return checks

    # =========================================================================
    # NOTIFICATION CREATION, GEMINI INTELLIGENCE, AND DISPATCH
    # =========================================================================

    def _generate_and_dispatch_notification(
        self,
        device_id: str,
        alert_type: str,
        priority: str,
        category: str,
        plant: str,
        telemetry: Dict[str, Any],
        profile: Dict[str, Any],
        location: Optional[Dict[str, Any]],
        weather: Optional[Dict[str, Any]],
        is_recovery: bool = False,
    ) -> Optional[Dict[str, Any]]:
        """Constructs notification payload, generates AI content, stores in DB, queues emails, and publishes MQTT."""
        now = datetime.now(timezone.utc)
        time_tag = int(now.timestamp())
        type_tag = f"RECOVERY_{alert_type}" if is_recovery else alert_type
        notification_id = f"gp-{device_id}-{type_tag}-{time_tag}"

        loc_str = LocationService.format_display_name(location)

        alert_context = {
            "type": type_tag,
            "priority": priority,
            "plant": plant,
            "location": loc_str,
            "telemetry": telemetry,
            "plant_profile": profile,
            "weather": weather,
        }

        # Generate contextual intelligence via Gemini with deterministic fallback
        gemini = self._get_gemini()
        if gemini:
            ai_data = gemini.generate_notification_content(alert_context)
        else:
            # Direct fallback if Gemini is not loaded
            ai_data = GeminiService.fallback_notification_content(None, alert_context)

        notification_record = {
            "notification_id": notification_id,
            "device_id": device_id,
            "plant": plant,
            "location": loc_str,
            "type": type_tag,
            "priority": priority,
            "title": ai_data.get("title", f"Greenhouse {type_tag}"),
            "summary": ai_data.get("summary", ""),
            "care_tip": ai_data.get("care_tip", ""),
            "email_status": "PENDING",
            "generated_at": now.isoformat(),
        }

        # Save to database
        try:
            self.database.save_notification(notification_record)
        except Exception as err:
            logger.error("Failed to save notification record to SQLite: %s", err)

        # Find subscribed recipient emails
        target_category = "RECOVERY" if is_recovery else category
        recipients = self.database.get_recipients_for_alert_type(target_category)

        # Critical alerts notify anyone who has critical/system enabled
        if priority == "CRITICAL" and not is_recovery:
            crit_recipients = self.database.get_recipients_for_alert_type("SYSTEM")
            recipients = list(set(recipients + crit_recipients))

        # Enqueue emails for background delivery
        for rec in recipients:
            if not self.database.notification_already_sent(notification_id, rec):
                self._email_queue.put((notification_id, rec, notification_record))

        # Publish notification event and status over MQTT
        self._publish_mqtt_notification(notification_record)

        return notification_record

    def _publish_mqtt_notification(self, notif: Dict[str, Any]):
        """Publish notification event and status state to MQTT topics."""
        if not self._mqtt_publish_callback:
            return

        import json

        device_id = notif.get("device_id", DEVICE_ID)
        notif_topic = f"greenpulse/{device_id}/notifications"
        status_topic = f"greenpulse/{device_id}/notification/status"

        try:
            payload = json.dumps(notif, ensure_ascii=False)
            # Event stream is QoS 1, not retained
            self._mqtt_publish_callback(notif_topic, payload, 1, False)

            # Latest status snapshot is QoS 1, retained
            status_payload = json.dumps({
                "device_id": device_id,
                "latest_notification": notif,
                "timestamp": notif.get("generated_at"),
            }, ensure_ascii=False)
            self._mqtt_publish_callback(status_topic, status_payload, 1, True)

        except Exception as err:
            logger.warning("Failed to publish notification to MQTT: %s", err)

    # =========================================================================
    # ASYNC EMAIL WORKER LOOP
    # =========================================================================

    def _email_worker_loop(self):
        """Background daemon processing the email delivery queue without blocking telemetry."""
        while self._worker_running:
            try:
                item = self._email_queue.get(timeout=1.0)
            except queue.Empty:
                continue

            notification_id, recipient, notif_data = item
            try:
                # Idempotency check: prevent duplicate deliveries
                if self.database.notification_already_sent(notification_id, recipient):
                    logger.debug("Skipping duplicate email for %s - %s", notification_id, recipient)
                    self._email_queue.task_done()
                    continue

                # Deliver outbound email via SmtpSender
                result = self.smtp_sender.send_notification_email(recipient, notif_data)
                status = result.get("status", "SMTP_ERROR")
                error_msg = result.get("error")

                # Log attempt
                self.database.log_email_attempt(notification_id, recipient, status, error_msg)

                # Update notification master record status
                self.database.update_notification_email_status(notification_id, status)

            except Exception as err:
                logger.exception("Unexpected error in email worker delivery to %s: %s", recipient, err)
                try:
                    self.database.log_email_attempt(notification_id, recipient, "INTERNAL_ERROR", str(err))
                except Exception:
                    pass
            finally:
                self._email_queue.task_done()

    # =========================================================================
    # RECIPIENT MANAGEMENT & TEST EMAIL
    # =========================================================================

    def send_test_email(self, email_address: str) -> Dict[str, Any]:
        """
        Send a test email to verify recipient connectivity.
        Enforces a 5-minute rate limit per recipient.
        """
        clean_email = email_address.strip().lower()
        if not SmtpSender.is_valid_email(clean_email):
            return {
                "success": False,
                "status": "REJECTED_INVALID_EMAIL",
                "error": f"Invalid email format: {clean_email}",
            }

        recipient_record = self.database.get_recipient_by_email(clean_email)
        now = datetime.now(timezone.utc)

        # Rate limiting check
        if recipient_record and recipient_record.get("last_test_email_at"):
            try:
                last_dt = datetime.fromisoformat(recipient_record["last_test_email_at"])
                if last_dt.tzinfo is None:
                    last_dt = last_dt.replace(tzinfo=timezone.utc)
                elapsed = (now - last_dt).total_seconds()
                if elapsed < self.TEST_EMAIL_RATE_LIMIT_SECONDS:
                    remaining = int(self.TEST_EMAIL_RATE_LIMIT_SECONDS - elapsed)
                    return {
                        "success": False,
                        "status": "RATE_LIMITED",
                        "error": f"Rate limit active. Please wait {remaining} seconds before sending another test email.",
                    }
            except Exception:
                pass

        # Send test email
        result = self.smtp_sender.send_test_email(clean_email)
        if result.get("success"):
            self.database.update_last_test_email(clean_email)
            # Log in delivery log
            test_id = f"test-{int(now.timestamp())}"
            self.database.log_email_attempt(test_id, clean_email, "ACCEPTED_BY_SMTP", None)

        return result

    def get_recipients(self) -> List[Dict[str, Any]]:
        """Return all notification recipients."""
        return self.database.get_all_notification_recipients()

    def add_recipient(self, email_address: str, preferences: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Add recipient with validation."""
        clean_email = email_address.strip().lower()
        if not SmtpSender.is_valid_email(clean_email):
            raise ValueError(f"Invalid email address: {clean_email}")

        rec_id = self.database.add_notification_recipient(clean_email, preferences)
        return {"id": rec_id, "email": clean_email}

    def update_recipient(self, email_address: str, preferences: Dict[str, Any]) -> bool:
        """Update recipient preferences."""
        clean_email = email_address.strip().lower()
        return self.database.update_recipient_preferences(clean_email, preferences)

    def remove_recipient(self, email_address: str) -> bool:
        """Delete recipient."""
        clean_email = email_address.strip().lower()
        return self.database.remove_notification_recipient(clean_email)

    def get_recent_notifications(self, limit: int = 20) -> List[Dict[str, Any]]:
        """Fetch recent notifications history."""
        return self.database.get_recent_notifications(DEVICE_ID, limit=limit)

    def stop(self):
        """Shut down background worker cleanly."""
        self._worker_running = False
