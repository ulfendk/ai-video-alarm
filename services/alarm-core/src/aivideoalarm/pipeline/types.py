"""Shared types passed between pipeline tiers."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any


class Decision(StrEnum):
    SUPPRESS = "suppress"
    ALARM = "alarm"
    AMBIGUOUS = "ambiguous"


@dataclass
class FrigateEvent:
    """Parsed subset of a `frigate/events` MQTT payload we actually use."""

    event_id: str
    camera: str
    label: str
    zones: list[str]
    top_score: float
    has_snapshot: bool
    has_clip: bool
    raw: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_mqtt_payload(cls, payload: dict[str, Any]) -> FrigateEvent:
        after = payload.get("after", payload)
        return cls(
            event_id=after["id"],
            camera=after["camera"],
            label=after["label"],
            zones=after.get("entered_zones") or after.get("zones") or [],
            top_score=float(after.get("top_score") or 0.0),
            has_snapshot=bool(after.get("has_snapshot")),
            has_clip=bool(after.get("has_clip")),
            raw=payload,
        )


@dataclass
class TierResult:
    """Output of any single tier."""

    decision: Decision
    confidence: float
    source: str  # "tier0" | "tier1" | "tier2"
    reasoning: str = ""
    rule_fired: str | None = None


@dataclass
class VerificationOutcome:
    """Final, fused decision for a Frigate event — what gets published to
    MQTT and written to the archive."""

    event: FrigateEvent
    decision: Decision
    confidence: float
    verification_source: str  # "tier0" | "tier1" | "tier1+tier2"
    reasoning: str
    rule_fired: str | None
    snapshot_url: str | None = None
    clip_url: str | None = None
