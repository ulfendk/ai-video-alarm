"""Debounce and door/window contact-sensor correlation.

Debounce collapses a single prolonged Frigate event (many sub-events as a
subject lingers) into one verified-alarm entity update instead of a storm
of separate ones. Door/window correlation raises confidence when a camera
event is corroborated by an actual contact-sensor state change — the
"forced entry" signal from the backlog's electronic-lock requirement.
"""

from __future__ import annotations

import time

from aivideoalarm.config import DoorWindowSensor

# States an HA binary_sensor (door/window contact) reports as "triggered".
# Matches whatever your statestream bridge forwards the entity's `state`
# attribute as — HA itself normally reports "on"/"off".
OPEN_STATES = {"on", "open", "true", "1"}


class Debouncer:
    def __init__(self, window_seconds: int) -> None:
        self._window_seconds = window_seconds
        self._last_seen: dict[tuple[str, str, str], float] = {}

    def should_process(self, camera: str, zone: str, label: str) -> bool:
        """Returns False if this camera/zone/label fired within the
        debounce window already."""
        key = (camera, zone, label)
        now = time.monotonic()
        last = self._last_seen.get(key)
        self._last_seen[key] = now
        return last is None or (now - last) > self._window_seconds


class DoorWindowCorrelator:
    """Tracks recent HA contact-sensor state changes (fed in externally via
    the HA state-change MQTT/websocket subscription — TODO: wire that
    subscription in main.py once the real entity_ids are known, see
    docs/clarifying-questions.md) and answers whether a camera event near
    a given camera coincides with one.
    """

    def __init__(self, sensors: list[DoorWindowSensor], correlation_window_seconds: int = 30) -> None:
        self._sensors_by_camera: dict[str, list[DoorWindowSensor]] = {}
        for sensor in sensors:
            if sensor.camera:
                self._sensors_by_camera.setdefault(sensor.camera, []).append(sensor)
        self._window = correlation_window_seconds
        self._last_open: dict[str, float] = {}  # entity_id -> monotonic time

    def record_sensor_open(self, entity_id: str) -> None:
        self._last_open[entity_id] = time.monotonic()

    def correlates_with_camera(self, camera: str) -> bool:
        sensors = self._sensors_by_camera.get(camera, [])
        now = time.monotonic()
        return any(
            (now - self._last_open.get(s.entity_id, -1e9)) <= self._window for s in sensors
        )
