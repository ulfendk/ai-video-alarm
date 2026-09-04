"""Combines Tier 0/1/(2) results into the final VerificationOutcome that
gets published to MQTT and archived.

Fusion rule: Tier 0 alarm/suppress is final (it's a direct config match —
treat it as intentional and authoritative). Otherwise take Tier 1's
decision; if Tier 1 was AMBIGUOUS and Tier 2 ran, Tier 2's decision wins.
All suppressions are logged, not discarded (docs/architecture.md /
docs/adr/0004) — that's the caller's responsibility via the archive
writer, not this function's.
"""

from __future__ import annotations

from aivideoalarm.pipeline.types import Decision, FrigateEvent, TierResult, VerificationOutcome


def fuse(
    event: FrigateEvent,
    tier0: TierResult,
    tier1: TierResult | None,
    tier2: TierResult | None,
) -> VerificationOutcome:
    if tier0.decision != Decision.AMBIGUOUS:
        return VerificationOutcome(
            event=event,
            decision=tier0.decision,
            confidence=tier0.confidence,
            verification_source="tier0",
            reasoning=tier0.reasoning,
            rule_fired=tier0.rule_fired,
        )

    if tier1 is None:
        # Shouldn't happen in the normal flow, but fail safe to ambiguous
        # rather than silently alarming or suppressing.
        return VerificationOutcome(
            event=event,
            decision=Decision.AMBIGUOUS,
            confidence=0.0,
            verification_source="tier0",
            reasoning="Tier 0 ambiguous and Tier 1 did not run.",
            rule_fired=None,
        )

    if tier1.decision != Decision.AMBIGUOUS or tier2 is None:
        return VerificationOutcome(
            event=event,
            decision=tier1.decision,
            confidence=tier1.confidence,
            verification_source="tier1",
            reasoning=tier1.reasoning,
            rule_fired=None,
        )

    return VerificationOutcome(
        event=event,
        decision=tier2.decision,
        confidence=tier2.confidence,
        verification_source="tier1+tier2",
        reasoning=f"tier1: {tier1.reasoning} | tier2: {tier2.reasoning}",
        rule_fired=None,
    )
