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
from dataclasses import dataclass
from datetime import date

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
    """In-memory daily call counter. TODO: back this with the SQLite
    archive DB so the cap survives a restart mid-day."""

    def __init__(self, daily_cap: int) -> None:
        self._daily_cap = daily_cap
        self._day: date | None = None
        self._count = 0

    def try_consume(self) -> bool:
        today = date.today()
        if self._day != today:
            self._day = today
            self._count = 0
        if self._count >= self._daily_cap:
            return False
        self._count += 1
        return True


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
        extra_context: str = "",
    ) -> TierResult:
        prompt = PROMPT_TEMPLATE.format(
            camera=camera,
            zone=zone,
            label=label,
            alarm_state=alarm_state.value,
            time_of_day="night" if extra_context else "day",  # TODO: pass real value
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
