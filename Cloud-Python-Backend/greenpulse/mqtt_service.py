import logging
import ssl

import paho.mqtt.client as mqtt

from greenpulse.config import Config
from greenpulse.database import Database
from greenpulse.plant_service import (
    PlantService,
    PlantConfigError,
)
from greenpulse.telemetry_service import (
    TelemetryService,
    TelemetryValidationError,
)


TELEMETRY_TOPIC = "greenpulse/device01/telemetry"
CONFIG_TOPIC = "greenpulse/device01/config"

DEVICE_ID = "device01"

logger = logging.getLogger("greenpulse.mqtt")


class MQTTService:
    """Handles MQTT communication for the GreenPulse backend."""

    def __init__(self):
        Config.validate()

        # Initialize database and plant service
        self.database = Database()
        self.plant_service = PlantService()

        # Restore the most recently selected crop after a restart
        self._restore_plant_configuration()

        # Create MQTT client
        self.client = mqtt.Client(
            callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
            client_id="greenpulse_backend"
        )

        # MQTT authentication
        self.client.username_pw_set(
            Config.MQTT_USERNAME,
            Config.MQTT_PASSWORD
        )

        # TLS security
        self.client.tls_set(
            cert_reqs=ssl.CERT_REQUIRED,
            tls_version=ssl.PROTOCOL_TLS_CLIENT
        )

        # MQTT callbacks
        self.client.on_connect = self._on_connect
        self.client.on_subscribe = self._on_subscribe
        self.client.on_message = self._on_message
        self.client.on_disconnect = self._on_disconnect

    def _restore_plant_configuration(self):
        """Restore the latest crop selection from SQLite."""

        stored_crop = (
            self.database.get_latest_plant_configuration(
                DEVICE_ID
            )
        )

        if stored_crop is None:
            logger.info(
                "No previous plant configuration found."
            )
            return

        self.plant_service.current_crop_id = (
            stored_crop["crop_id"]
        )

        logger.info(
            "Restored plant configuration. "
            "Crop=%s Category=%s",
            stored_crop["name"],
            stored_crop["category"]
        )

    def _on_connect(
        self,
        client,
        userdata,
        flags,
        reason_code,
        properties
    ):
        """Called when the backend connects to HiveMQ."""

        if reason_code == 0:
            logger.info(
                "Connected to MQTT broker %s:%s",
                Config.MQTT_HOST,
                Config.MQTT_PORT
            )

            # Subscribe to sensor telemetry
            result, message_id = client.subscribe(
                TELEMETRY_TOPIC,
                qos=0
            )

            if result == mqtt.MQTT_ERR_SUCCESS:
                logger.info(
                    "Subscription request sent. "
                    "Topic=%s MessageID=%s",
                    TELEMETRY_TOPIC,
                    message_id
                )
            else:
                logger.error(
                    "Failed to subscribe to telemetry topic. "
                    "Error=%s",
                    result
                )

            # Subscribe to plant configuration
            result, message_id = client.subscribe(
                CONFIG_TOPIC,
                qos=0
            )

            if result == mqtt.MQTT_ERR_SUCCESS:
                logger.info(
                    "Subscription request sent. "
                    "Topic=%s MessageID=%s",
                    CONFIG_TOPIC,
                    message_id
                )
            else:
                logger.error(
                    "Failed to subscribe to config topic. "
                    "Error=%s",
                    result
                )

        else:
            logger.error(
                "MQTT connection failed. Reason=%s",
                reason_code
            )

    def _on_subscribe(
        self,
        client,
        userdata,
        mid,
        reason_code_list,
        properties
    ):
        """Called when HiveMQ confirms a subscription."""

        logger.info(
            "MQTT subscription confirmed. "
            "MessageID=%s Result=%s",
            mid,
            reason_code_list
        )

    def _on_message(
        self,
        client,
        userdata,
        message
    ):
        """Route MQTT messages to the correct service."""

        try:
            payload = message.payload.decode("utf-8")

        except UnicodeDecodeError:
            logger.warning(
                "MQTT message rejected: invalid UTF-8. "
                "Topic=%s",
                message.topic
            )
            return

        logger.info(
            "MQTT message received. Topic=%s",
            message.topic
        )

        if message.topic == TELEMETRY_TOPIC:
            self._handle_telemetry(payload)

        elif message.topic == CONFIG_TOPIC:
            self._handle_plant_configuration(payload)

        else:
            logger.warning(
                "Message received from unexpected topic: %s",
                message.topic
            )

    def _handle_telemetry(self, payload: str):
        """Validate and store sensor telemetry."""

        try:
            telemetry = (
                TelemetryService.parse_and_validate(
                    payload
                )
            )

            logger.info(
                "Telemetry validation passed. Device=%s",
                telemetry["device_id"]
            )

            record_id = self.database.save_telemetry(
                telemetry
            )

            logger.info(
                "Telemetry stored successfully. "
                "RecordID=%s Device=%s "
                "Temperature=%s Humidity=%s "
                "SoilMoisture=%s pH=%s MQ135Raw=%s",
                record_id,
                telemetry["device_id"],
                telemetry["temperature"],
                telemetry["humidity"],
                telemetry["soil_moisture"],
                telemetry["ph"],
                telemetry["mq135_raw"]
            )

        except TelemetryValidationError as error:
            logger.warning(
                "Telemetry validation failed. Reason=%s",
                error
            )

        except Exception:
            logger.exception(
                "Unexpected error while processing telemetry."
            )

    def _handle_plant_configuration(
        self,
        payload: str
    ):
        """Validate and store a greenhouse crop selection."""

        try:
            crop = (
                self.plant_service.parse_and_set_crop(
                    payload
                )
            )

            record_id = (
                self.database.save_plant_configuration(
                    DEVICE_ID,
                    crop
                )
            )

            logger.info(
                "Plant configuration updated successfully. "
                "RecordID=%s Crop=%s Category=%s",
                record_id,
                crop["name"],
                crop["category"]
            )

        except PlantConfigError as error:
            logger.warning(
                "Plant configuration rejected. Reason=%s",
                error
            )

        except Exception:
            logger.exception(
                "Unexpected error while processing "
                "plant configuration."
            )

    def _on_disconnect(
        self,
        client,
        userdata,
        disconnect_flags,
        reason_code,
        properties
    ):
        """Called when the MQTT connection closes."""

        if reason_code == 0:
            logger.info(
                "MQTT client disconnected normally."
            )
        else:
            logger.warning(
                "MQTT client disconnected unexpectedly. "
                "Reason=%s",
                reason_code
            )

    def connect(self):
        """Connect to HiveMQ Cloud and process MQTT messages."""

        logger.info(
            "Connecting to MQTT broker..."
        )

        self.client.connect(
            Config.MQTT_HOST,
            Config.MQTT_PORT,
            keepalive=60
        )

        self.client.loop_forever()