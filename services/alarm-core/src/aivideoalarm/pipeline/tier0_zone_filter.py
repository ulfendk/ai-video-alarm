"""Tier 0: the zone+label+time-window rule matrix.

This is deliberately the cheapest, most-certain tier — pure config lookup,
no inference. It's where the literal "cat in the backyard" case from the
backlog gets handled directly: a rule like camera=*, zone=backyard,
label=cat, decision=suppress needs no ML at all.

Frigate's own zone/mask config is the first filter before an event even
reaches alarm-core; this tier is the project's own rule layer on top of
that. See docs/architecture.md.
"""

from __future__ import annotations

from datetime import datetime, time

from aivideoalarm.alarm_state import AlarmState
from aivideoalarm.config import ZoneRule
from aivideoalarm.pipeline.types import Decision, FrigateEvent, TierResult


def _matches(pattern: str, value: str) -> bool:
    return pattern == "*" or pattern == value


def _in_time_window(window: str | None, now: time) -> bool:
    if window is None:
        return True
    start_str, end_str = window.split("-")
    start = time.fromisoformat(start_str)
    end = time.fromisoformat(end_str)
    if start <= end:
        return start <= now <= end
    return now >= start or now <= end  # window spans midnight


def evaluate(
    event: FrigateEvent,
    rules: list[ZoneRule],
    alarm_state: AlarmState,
    now: datetime | None = None,
) -> TierResult:
    """Evaluate the rule matrix in order; first match wins. No match ->
    AMBIGUOUS, deferring to Tier 1."""
    now = now or datetime.now()
    event_zones = event.zones or ["*"]

    for rule in rules:
        if not _matches(rule.camera, event.camera):
            continue
        if not any(_matches(rule.zone, z) for z in event_zones):
            continue
        if not _matches(rule.label, event.label):
            continue
        if alarm_state.value not in rule.alarm_states:
            continue
        if not _in_time_window(rule.time_window, now.time()):
            continue

        decision = {
            "suppress": Decision.SUPPRESS,
            "alarm": Decision.ALARM,
            "escalate": Decision.AMBIGUOUS,
        }[rule.decision]
        return TierResult(
            decision=decision,
            confidence=1.0 if decision != Decision.AMBIGUOUS else 0.5,
            source="tier0",
            reasoning=f"Matched rule: camera={rule.camera} zone={rule.zone} label={rule.label}",
            rule_fired=f"{rule.camera}/{rule.zone}/{rule.label}",
        )

    return TierResult(
        decision=Decision.AMBIGUOUS,
        confidence=0.0,
        source="tier0",
        reasoning="No zone/label/time-window rule matched; defer to Tier 1.",
    )
