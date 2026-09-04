"""MQTT client: consumes Frigate's events, publishes verified-alarm
entities and HA MQTT Discovery configs.

Schema: docs/adr/0003-mqtt-schema-and-ha-discovery.md
"""

from __future__ import annotations

import json
import logging
from collections.abc import Callable
from typing import Any

import paho.mqtt.client as mqtt

from aivideoalarm.config import Settings

logger = logging.getLogger(__name__)

DISCOVERY_PREFIX = "homeassistant"
APP_PREFIX = "aivideoalarm"
STATUS_TOPIC = f"{APP_PREFIX}/system/status"
ALARM_STATE_TOPIC = f"{APP_PREFIX}/system/alarm_panel/state"
ALARM_COMMAND_TOPIC = f"{APP_PREFIX}/system/alarm_panel/set"

FrigateEventHandler = Callable[[dict[str, Any]], None]
AlarmCommandHandler = Callable[[str], None]
DoorWindowStateHandler = Callable[[str, str], None]  # (entity_id, state)


class AlarmMqttClient:
    """Thin wrapper around paho-mqtt with the topic conventions this
    project uses. Kept deliberately dumb — routing/decision logic lives in
    the pipeline modules, not here.
    """

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._client = mqtt.Client(
            client_id="aivideoalarm-core",
            callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
        )
        if settings.mqtt_username:
            self._client.username_pw_set(settings.mqtt_username, settings.mqtt_password)
        self._client.will_set(STATUS_TOPIC, payload="offline", retain=True)

        self._on_frigate_event: FrigateEventHandler | None = None
        self._on_alarm_command: AlarmCommandHandler | None = None
        self._on_door_window_state: DoorWindowStateHandler | None = None
        self._door_window_topics: dict[str, str] = {}  # topic -> entity_id

        self._client.on_connect = self._handle_connect
        self._client.on_message = self._handle_message

    def on_frigate_event(self, handler: FrigateEventHandler) -> None:
        self._on_frigate_event = handler

    def on_alarm_command(self, handler: AlarmCommandHandler) -> None:
        self._on_alarm_command = handler

    def on_door_window_state(self, handler: DoorWindowStateHandler) -> None:
        self._on_door_window_state = handler

    def configure_door_window_topics(self, entity_ids: list[str], base_topic: str) -> None:
        """Builds the statestream topic for each door/window entity_id
        (domain.object_id -> <base_topic>/<domain>/<object_id>/state) so
        _handle_connect subscribes to them and _handle_message can map an
        incoming message back to its entity_id. See
        Settings.ha_statestream_base_topic in config.py."""
        self._door_window_topics.clear()
        for entity_id in entity_ids:
            domain, _, object_id = entity_id.partition(".")
            if not object_id:
                logger.warning("Skipping malformed entity_id: %r", entity_id)
                continue
            topic = f"{base_topic}/{domain}/{object_id}/state"
            self._door_window_topics[topic] = entity_id

    def connect(self) -> None:
        self._client.connect(self._settings.mqtt_host, self._settings.mqtt_port)
        self._client.loop_start()

    def disconnect(self) -> None:
        self.publish(STATUS_TOPIC, "offline", retain=True)
        self._client.loop_stop()
        self._client.disconnect()

    def _handle_connect(self, client, userdata, flags, reason_code, properties=None) -> None:
        logger.info("MQTT connected: %s", reason_code)
        client.subscribe("frigate/events")
        client.subscribe(ALARM_COMMAND_TOPIC)
        for topic in self._door_window_topics:
            client.subscribe(topic)
        self.publish(STATUS_TOPIC, "online", retain=True)

    def _handle_message(self, client, userdata, msg) -> None:
        if msg.topic == "frigate/events":
            if self._on_frigate_event is None:
                return
            try:
                payload = json.loads(msg.payload)
            except json.JSONDecodeError:
                logger.warning("Malformed frigate/events payload, skipping")
                return
            self._on_frigate_event(payload)
        elif msg.topic == ALARM_COMMAND_TOPIC:
            if self._on_alarm_command is not None:
                self._on_alarm_command(msg.payload.decode())
        elif msg.topic in self._door_window_topics:
            if self._on_door_window_state is not None:
                entity_id = self._door_window_topics[msg.topic]
                self._on_door_window_state(entity_id, msg.payload.decode().strip())

    def publish(self, topic: str, payload: str | dict, retain: bool = False) -> None:
        if isinstance(payload, dict):
            payload = json.dumps(payload)
        self._client.publish(topic, payload, retain=retain)

    def publish_alarm_state(self, state: str) -> None:
        self.publish(ALARM_STATE_TOPIC, state, retain=True)

    def publish_verified_alarm(
        self,
        camera: str,
        zone: str,
        payload: dict[str, Any],
        is_on: bool,
    ) -> None:
        base = f"{APP_PREFIX}/{camera}/{zone}/verified_alarm"
        self.publish(base, payload, retain=True)
        self.publish(f"{base}/state", "ON" if is_on else "OFF", retain=True)

    def publish_discovery_binary_sensor(self, camera: str, zone: str) -> None:
        """Publish an HA MQTT Discovery config for a per-camera/zone
        verified-alarm binary_sensor. Idempotent — safe to call on every
        startup."""
        object_id = f"aivideoalarm_{camera}_{zone}"
        config_topic = f"{DISCOVERY_PREFIX}/binary_sensor/{object_id}/config"
        state_topic = f"{APP_PREFIX}/{camera}/{zone}/verified_alarm/state"
        config = {
            "name": f"{camera} {zone} verified alarm",
            "unique_id": object_id,
            "state_topic": state_topic,
            "payload_on": "ON",
            "payload_off": "OFF",
            "device_class": "motion",
            "availability_topic": STATUS_TOPIC,
            "payload_available": "online",
            "payload_not_available": "offline",
        }
        self.publish(config_topic, config, retain=True)

    def publish_discovery_alarm_panel(self) -> None:
        object_id = "aivideoalarm_system"
        config_topic = f"{DISCOVERY_PREFIX}/alarm_control_panel/{object_id}/config"
        config = {
            "name": "AI Video Alarm",
            "unique_id": object_id,
            "state_topic": ALARM_STATE_TOPIC,
            "command_topic": ALARM_COMMAND_TOPIC,
            "availability_topic": STATUS_TOPIC,
            "payload_available": "online",
            "payload_not_available": "offline",
            "supported_features": ["arm_home", "arm_away", "arm_night"],
        }
        self.publish(config_topic, config, retain=True)
