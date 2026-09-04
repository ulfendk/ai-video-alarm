"""Entrypoint: wires MQTT, Frigate client, the escalation pipeline,
archive, and the FastAPI app together, then runs uvicorn.

This is the scaffold's integration point — the individual pieces
(pipeline tiers, archive, MQTT schema) are unit-testable in isolation;
this module is what a real deployment actually runs. See
docs/clarifying-questions.md for what's still needed before this can run
against a live Frigate/MQTT/HA instance (real camera/zone names, entity
IDs, credentials).
"""

from __future__ import annotations

import asyncio
import logging

import uvicorn

from aivideoalarm.alarm_state import AlarmStateMachine
from aivideoalarm.api import create_app
from aivideoalarm.archive.quota_pruner import QuotaPruner
from aivideoalarm.archive.writer import ArchiveWriter
from aivideoalarm.config import load_app_config, load_settings
from aivideoalarm.frigate_client import FrigateClient
from aivideoalarm.mqtt_client import AlarmMqttClient
from aivideoalarm.pipeline import fusion, tier0_zone_filter, tier1_local, tier2_cloud
from aivideoalarm.pipeline.types import Decision, FrigateEvent
from aivideoalarm.suppression.rules import Debouncer, DoorWindowCorrelator

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class AlarmCoreApp:
    def __init__(self) -> None:
        self.settings = load_settings()
        self.app_config = load_app_config(self.settings)

        self.alarm_state = AlarmStateMachine()
        self.mqtt = AlarmMqttClient(self.settings)
        self.frigate = FrigateClient(self.settings.frigate_url)
        self.archive_writer = ArchiveWriter(self.settings.archive_path, self.settings.db_path)
        self.quota_pruner = QuotaPruner(self.settings.db_path, self.settings.archive_quota_gb)
        self.debouncer = Debouncer(self.app_config.escalation.debounce_seconds)
        self.door_window = DoorWindowCorrelator(self.app_config.door_window_sensors)

        self.cloud_provider: tier2_cloud.CloudVisionProvider
        if self.settings.anthropic_api_key:
            self.cloud_provider = tier2_cloud.AnthropicVisionProvider(self.settings.anthropic_api_key)
        else:
            logger.warning("No ANTHROPIC_API_KEY configured; Tier 2 escalation disabled.")
            self.cloud_provider = tier2_cloud.NoOpVisionProvider()
        self.call_budget = tier2_cloud.DailyCallBudget(self.settings.cloud_ai_daily_call_cap)

        self._cameras_by_name = {c.frigate_camera: c for c in self.app_config.cameras}
        self._loop: asyncio.AbstractEventLoop | None = None

        self.mqtt.on_frigate_event(self._on_frigate_event_sync)
        self.mqtt.on_alarm_command(self._on_alarm_command)

    def publish_discovery(self) -> None:
        self.mqtt.publish_discovery_alarm_panel()
        for camera in self.app_config.cameras:
            for zone in camera.zones or ["default"]:
                self.mqtt.publish_discovery_binary_sensor(camera.frigate_camera, zone)

    def _on_alarm_command(self, command: str) -> None:
        try:
            new_state = self.alarm_state.handle_command(command)
        except ValueError:
            logger.warning("Ignoring unknown alarm command: %r", command)
            return
        self.mqtt.publish_alarm_state(new_state.value)

    def _on_frigate_event_sync(self, payload: dict) -> None:
        """paho-mqtt callbacks are sync; bridge into the async pipeline."""
        if self._loop is None:
            logger.warning("Event loop not ready, dropping frigate event")
            return
        asyncio.run_coroutine_threadsafe(self._handle_frigate_event(payload), self._loop)

    async def _handle_frigate_event(self, payload: dict) -> None:
        event = FrigateEvent.from_mqtt_payload(payload)
        camera = self._cameras_by_name.get(event.camera)
        if camera is None:
            logger.debug("Ignoring event for unconfigured camera %s", event.camera)
            return

        zone = event.zones[0] if event.zones else "default"
        if not self.debouncer.should_process(event.camera, zone, event.label):
            return

        tier0 = tier0_zone_filter.evaluate(event, self.app_config.zone_rules, self.alarm_state.state)

        tier1 = None
        tier2 = None
        if tier0.decision == Decision.AMBIGUOUS and event.has_snapshot:
            snapshot = await self.frigate.get_snapshot(event.event_id)
            # TODO: pull a real multi-frame burst from the clip for the
            # temporal-consistency check; tier1_local currently receives
            # an empty box list (neutral 0.5 score) until that's wired in.
            tier1 = tier1_local.evaluate(event, camera, snapshot, boxes=[])

            if tier1.decision == Decision.AMBIGUOUS:
                is_night = False  # TODO: derive from HA's sun.sun, per ADR
                if tier2_cloud.should_escalate(
                    tier1.confidence, zone, self.alarm_state.state, self.app_config.escalation, is_night
                ) and self.call_budget.try_consume():
                    tier2 = await self.cloud_provider.classify(
                        snapshot, event.camera, zone, event.label, self.alarm_state.state
                    )

        outcome = fusion.fuse(event, tier0, tier1, tier2)

        if self.door_window.correlates_with_camera(event.camera) and outcome.decision != Decision.SUPPRESS:
            outcome.confidence = min(1.0, outcome.confidence + 0.2)
            outcome.reasoning += " | corroborated by door/window sensor"

        self.mqtt.publish_verified_alarm(
            event.camera, zone, outcome.__dict__, is_on=(outcome.decision == Decision.ALARM)
        )

        if outcome.decision == Decision.ALARM:
            self.alarm_state.trigger()
            self.mqtt.publish_alarm_state(self.alarm_state.state.value)
            snapshot_bytes = await self.frigate.get_snapshot(event.event_id) if event.has_snapshot else None
            clip_bytes = await self.frigate.get_clip(event.event_id) if event.has_clip else None
            self.archive_writer.write(outcome, snapshot_bytes, clip_bytes)
            self.quota_pruner.prune_if_needed()

    async def run(self) -> None:
        self._loop = asyncio.get_running_loop()
        self.mqtt.connect()
        self.publish_discovery()

        app = create_app(self.settings, self.alarm_state)
        config = uvicorn.Config(app, host=self.settings.api_host, port=self.settings.api_port)
        server = uvicorn.Server(config)
        try:
            await server.serve()
        finally:
            self.mqtt.disconnect()
            await self.frigate.aclose()


def main() -> None:
    asyncio.run(AlarmCoreApp().run())


if __name__ == "__main__":
    main()
