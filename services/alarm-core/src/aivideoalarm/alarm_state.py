"""The alarm state machine — alarm-core is the authoritative owner of arm
state (see docs/architecture.md "What alarm-core does not own"). HA is a
client of this state, not the other way around: lock actuation and
presence-simulation start/stop live in HA automations that subscribe to
`aivideoalarm/system/alarm_panel/state` and react to it.

Per the user's confirmed setup, there is no separate presence/device-tracker
signal — the arm/disarm state itself is what currently drives presence
simulation, so `is_away` below is derived directly from this state machine
rather than a separate integration.
"""

from __future__ import annotations

from enum import StrEnum


class AlarmState(StrEnum):
    DISARMED = "disarmed"
    ARMED_HOME = "armed_home"
    ARMED_AWAY = "armed_away"
    ARMED_NIGHT = "armed_night"
    PENDING = "pending"
    ARMING = "arming"
    TRIGGERED = "triggered"


# Command strings accepted on aivideoalarm/system/alarm_panel/set, matching
# HA's MQTT Alarm Control Panel contract.
_COMMAND_TO_STATE = {
    "DISARM": AlarmState.DISARMED,
    "ARM_HOME": AlarmState.ARMED_HOME,
    "ARM_AWAY": AlarmState.ARMED_AWAY,
    "ARM_NIGHT": AlarmState.ARMED_NIGHT,
}


class AlarmStateMachine:
    def __init__(self, initial: AlarmState = AlarmState.DISARMED) -> None:
        self._state = initial

    @property
    def state(self) -> AlarmState:
        return self._state

    @property
    def is_away(self) -> bool:
        """True when nobody is expected home — the strongest suppression/
        escalation-policy signal available in this deployment."""
        return self._state == AlarmState.ARMED_AWAY

    def handle_command(self, command: str) -> AlarmState:
        """Apply an incoming MQTT command. Real deployments will likely
        want arm/exit delays (TODO); this is the minimal direct-transition
        version for the initial scaffold."""
        new_state = _COMMAND_TO_STATE.get(command.strip().upper())
        if new_state is None:
            raise ValueError(f"Unknown alarm command: {command!r}")
        self._state = new_state
        return self._state

    def trigger(self) -> AlarmState:
        """Called when a verified alarm fires while armed."""
        if self._state in (AlarmState.ARMED_HOME, AlarmState.ARMED_AWAY, AlarmState.ARMED_NIGHT):
            self._state = AlarmState.TRIGGERED
        return self._state
