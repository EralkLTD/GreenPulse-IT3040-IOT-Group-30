"""
GreenPulse - Daily Summary Service

Scheduled background service that aggregates daily greenhouse performance,
current plant, sensor readings, and weather forecast, generates concise AI
recommendations, and delivers daily email summaries to subscribed recipients.
"""
from datetime import datetime, timezone
import logging
from typing import Dict, Any, Optional

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

from greenpulse.config import Config
from greenpulse.database import Database
from greenpulse.email_service import SmtpSender
from greenpulse.gemini_service import GeminiService
from greenpulse.location_service import LocationService
from greenpulse.weather_service import WeatherService

logger = logging.getLogger("greenpulse.daily_summary")

DEVICE_ID = "device01"


class DailySummaryService:
    """Manages scheduled daily greenhouse status reports."""

    def __init__(
        self,
        database: Optional[Database] = None,
        smtp_sender: Optional[SmtpSender] = None,
        gemini_service: Optional[GeminiService] = None,
        weather_service: Optional[WeatherService] = None,
    ):
        self.database = database or Database()
        self.smtp_sender = smtp_sender or SmtpSender()
        self.gemini_service = gemini_service
        self.weather_service = weather_service or WeatherService()
        self.scheduler: Optional[BackgroundScheduler] = None

    def _get_gemini(self) -> Optional[GeminiService]:
        if self.gemini_service is None:
            try:
                self.gemini_service = GeminiService()
            except Exception as err:
                logger.debug("Gemini unavailable for daily summary: %s", err)
        return self.gemini_service

    def start(self, cron_time: Optional[str] = None):
        """Start the background scheduler for daily summaries."""
        time_str = cron_time or Config.NOTIFICATION_DAILY_SUMMARY_TIME or "08:00"
        try:
            hour_str, min_str = time_str.split(":")
            hour = int(hour_str)
            minute = int(min_str)
        except Exception:
            hour, minute = 8, 0

        self.scheduler = BackgroundScheduler()
        trigger = CronTrigger(hour=hour, minute=minute)
        self.scheduler.add_job(
            self.send_daily_summary_now,
            trigger=trigger,
            id="greenpulse_daily_summary",
            name="GreenPulse Greenhouse Daily Summary",
            replace_existing=True,
        )
        self.scheduler.start()
        logger.info("Daily summary scheduler started: scheduled daily at %02d:%02d UTC", hour, minute)

    def stop(self):
        """Stop scheduler."""
        if self.scheduler and self.scheduler.running:
            self.scheduler.shutdown(wait=False)
            logger.info("Daily summary scheduler stopped.")

    def send_daily_summary_now(self) -> Dict[str, Any]:
        """
        Gathers current greenhouse context, generates AI summary,
        and sends to all subscribed recipients.
        """
        now = datetime.now(timezone.utc)
        today_str = now.strftime("%Y-%m-%d")

        # 1. Gather context
        plant_cfg = self.database.get_latest_plant_configuration(DEVICE_ID)
        plant_name = plant_cfg.get("name") or plant_cfg.get("crop_name") if plant_cfg else "Greenhouse Crop"

        location_row = self.database.get_latest_device_location(DEVICE_ID)
        location_str = LocationService.format_display_name(location_row)

        profile = self.database.get_latest_plant_profile(DEVICE_ID) or {}

        # Fetch latest telemetry directly from database
        telemetry = {}
        try:
            conn = self.database._get_connection()
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT air_temperature, humidity, soil_moisture, soil_temperature, light, received_at
                FROM telemetry
                WHERE device_id = ?
                ORDER BY id DESC LIMIT 1
                """,
                (DEVICE_ID,)
            )
            row = cursor.fetchone()
            if row:
                telemetry = {
                    "air_temperature": row[0],
                    "humidity": row[1],
                    "soil_moisture": row[2],
                    "soil_temperature": row[3],
                    "light": row[4],
                    "received_at": row[5],
                }
            conn.close()
        except Exception as err:
            logger.warning("Could not read latest telemetry for daily summary: %s", err)

        # Weather context
        weather = None
        if location_row and location_row.get("latitude") and location_row.get("longitude"):
            try:
                weather = self.weather_service.get_weather(
                    location_row["latitude"],
                    location_row["longitude"]
                )
            except Exception as err:
                logger.debug("Weather fetch for daily summary skipped: %s", err)

        summary_context = {
            "date": today_str,
            "plant": plant_name,
            "location": location_str,
            "telemetry": telemetry,
            "plant_profile": profile,
            "weather": weather,
        }

        # 2. Generate AI summary
        gemini = self._get_gemini()
        if gemini:
            ai_data = gemini.generate_daily_summary(summary_context)
        else:
            ai_data = GeminiService.fallback_daily_summary(None, summary_context)

        summary_data = {
            "date": today_str,
            "plant": plant_name,
            "location": location_str,
            "telemetry": telemetry,
            "weather": weather,
            "overall_status": ai_data.get("overall_status", "GOOD"),
            "ai_recommendation": f"{ai_data.get('summary', '')} {ai_data.get('recommendations', '')}".strip(),
            "weather_outlook": ai_data.get("weather_outlook", ""),
        }

        # 3. Recipients
        recipients = self.database.get_recipients_for_alert_type("DAILY_SUMMARY")
        summary_id = f"gp-{DEVICE_ID}-DAILY_SUMMARY-{today_str}"

        delivered_count = 0
        for rec in recipients:
            if self.database.notification_already_sent(summary_id, rec):
                logger.debug("Daily summary already sent to %s for %s", rec, today_str)
                continue

            res = self.smtp_sender.send_daily_summary_email(rec, summary_data)
            status = res.get("status", "SMTP_ERROR")
            self.database.log_email_attempt(summary_id, rec, status, res.get("error"))
            if res.get("success"):
                delivered_count += 1

        logger.info(
            "Daily summary dispatch completed for %s: %d/%d delivered",
            today_str,
            delivered_count,
            len(recipients)
        )

        return {
            "summary_id": summary_id,
            "delivered": delivered_count,
            "total_recipients": len(recipients),
            "summary_data": summary_data,
        }
