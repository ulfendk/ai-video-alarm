"""Tier 2: Claude vision escalation.

Only called when Tier 1 is AMBIGUOUS *and* stakes are high (armed_away/
armed_night, or a configured sensitive zone) — see should_escalate below.
Rate-limited to a small daily cap to match the user's minimal (~$5-10/mo)
budget; degrades gracefully to Tier-1-only once exceeded rather than
failing the pipeline.
"""

from __future__ import annotations

import base64
import json
import logging
import sqlite3
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path

import anthropic

from aivideoalarm.alarm_state import AlarmState
from aivideoalarm.config import EscalationPolicy
from aivideoalarm.pipeline.types import Decision, TierResult

logger = logging.getLogger(__name__)

MODEL = "claude-sonnet-5"

PROMPT_TEMPLATE = """You are a home security verification assistant. Review the attached \
image(s) and decide whether this event is worth alerting the homeowner about.

Context:
- Camera: {camera}
- Zone: {zone}
- Detected label (from the primary detector, may be wrong): {label}
- Current alarm state: {alarm_state}
- Time of day: {time_of_day}
- Additional context: {extra_context}

Respond with ONLY a JSON object of the form:
{{"is_concern": bool, "subject": string, "confidence": float, "reasoning": string}}
"""


class DailyCallBudget:
    """Daily Tier-2 call counter, persisted to SQLite (the same DB the
    archive uses) so the cap survives a restart mid-day rather than
    silently resetting."""

    _SCHEMA = """
    CREATE TABLE IF NOT EXISTS cloud_call_budget (
        day TEXT PRIMARY KEY,
        count INTEGER NOT NULL DEFAULT 0
    );
    """

    def __init__(self, daily_cap: int, db_path: Path) -> None:
        self._daily_cap = daily_cap
        self._db_path = db_path
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(self._db_path) as conn:
            conn.executescript(self._SCHEMA)

    def try_consume(self) -> bool:
        today = date.today().isoformat()
        with sqlite3.connect(self._db_path) as conn:
            row = conn.execute(
                "SELECT count FROM cloud_call_budget WHERE day = ?", (today,)
            ).fetchone()
            count = row[0] if row else 0
            if count >= self._daily_cap:
                return False
            conn.execute(
                """INSERT INTO cloud_call_budget (day, count) VALUES (?, 1)
                   ON CONFLICT(day) DO UPDATE SET count = count + 1""",
                (today,),
            )
        return True


def is_night(policy: EscalationPolicy, when: datetime | None = None) -> bool:
    """Simple clock-hour night window — see EscalationPolicy.night_start_hour
    / night_end_hour in config.py for the reasoning."""
    when = when or datetime.now()
    hour = when.hour
    start, end = policy.night_start_hour, policy.night_end_hour
    if start <= end:
        return start <= hour < end
    return hour >= start or hour < end  # window spans midnight


def should_escalate(
    tier1_confidence: float,
    zone: str,
    alarm_state: AlarmState,
    policy: EscalationPolicy,
    is_night: bool,
) -> bool:
    low, high = policy.tier1_ambiguous_confidence_band
    if is_night:
        low = max(0.0, low - policy.night_escalation_bias)
        high = min(1.0, high + policy.night_escalation_bias)

    is_ambiguous = low <= tier1_confidence <= high
    high_stakes = alarm_state in (AlarmState.ARMED_AWAY, AlarmState.ARMED_NIGHT) or (
        zone in policy.sensitive_zones
    )
    return is_ambiguous and high_stakes


@dataclass
class CloudVisionProvider:
    """Adapter interface — swapping vendors is a config/class change, not
    a pipeline rewrite. Anthropic is the only implementation for v1 per
    the user's choice; a stub/no-op provider is available for tests and
    for local runs without an API key configured."""

    async def classify(
        self,
        image_bytes: bytes,
        camera: str,
        zone: str,
        label: str,
        alarm_state: AlarmState,
        is_night: bool = False,
        extra_context: str = "",
    ) -> TierResult:
        raise NotImplementedError


class AnthropicVisionProvider(CloudVisionProvider):
    def __init__(self, api_key: str) -> None:
        self._client = anthropic.AsyncAnthropic(api_key=api_key)

    async def classify(
        self,
        image_bytes: bytes,
        camera: str,
        zone: str,
        label: str,
        alarm_state: AlarmState,
        is_night: bool = False,
        extra_context: str = "",
    ) -> TierResult:
        prompt = PROMPT_TEMPLATE.format(
            camera=camera,
            zone=zone,
            label=label,
            alarm_state=alarm_state.value,
            time_of_day="night" if is_night else "day",
            extra_context=extra_context or "none",
        )
        image_b64 = base64.b64encode(image_bytes).decode()
        response = await self._client.messages.create(
            model=MODEL,
            max_tokens=512,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image",
                            "source": {
                                "type": "base64",
                                "media_type": "image/jpeg",
                                "data": image_b64,
                            },
                        },
                        {"type": "text", "text": prompt},
                    ],
                }
            ],
        )
        text = response.content[0].text  # type: ignore[union-attr]
        try:
            verdict = json.loads(text)
        except json.JSONDecodeError:
            logger.warning("Claude returned non-JSON verdict, treating as ambiguous: %r", text)
            return TierResult(
                decision=Decision.AMBIGUOUS,
                confidence=0.5,
                source="tier2",
                reasoning="Failed to parse cloud verdict",
            )

        decision = Decision.ALARM if verdict.get("is_concern") else Decision.SUPPRESS
        return TierResult(
            decision=decision,
            confidence=float(verdict.get("confidence", 0.5)),
            source="tier2",
            reasoning=verdict.get("reasoning", ""),
        )


class NoOpVisionProvider(CloudVisionProvider):
    """Used when no API key is configured, or the daily budget is
    exhausted — pipeline falls back to Tier-1-only decisions."""

    async def classify(self, *args, **kwargs) -> TierResult:
        return TierResult(
            decision=Decision.AMBIGUOUS,
            confidence=0.5,
            source="tier2",
            reasoning="Cloud escalation unavailable (no API key or budget exhausted).",
        )
