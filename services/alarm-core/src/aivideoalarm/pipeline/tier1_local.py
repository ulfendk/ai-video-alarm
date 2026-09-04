"""Tier 1: local re-classification + multi-frame temporal-consistency
check, running on the host's CPU/NVIDIA GPU (the Coral stays with Frigate
— see docs/adr/0001 and docs/adr/0002).

Two sub-checks, deliberately kept independent so the cheap one can run
even before a real model is wired in:

- Temporal consistency: compares bounding-box trajectory/size across a
  short frame burst. A bird's fast, small, erratic motion vs. a person's
  larger, sustained, path-like motion is a strong, cheap, model-free
  discriminator — this is the direct fix for the "bird near a bike" false
  positive in the backlog. Runs first.
- Re-classification: a heavier-than-Frigate's-own-detector model, run only
  on already-filtered candidate events (Frigate + Tier 0 already thinned
  the stream). TODO: wire in a real ONNX model; `_classify` is currently a
  stub returning a neutral (ambiguous) result so the pipeline is runnable
  end-to-end before that model is chosen/trained.
"""

from __future__ import annotations

from dataclasses import dataclass

from aivideoalarm.config import CameraProfile
from aivideoalarm.pipeline.types import Decision, FrigateEvent, TierResult

# Confidence band Tier 0 -> Tier 1 treats as genuinely ambiguous, before
# any night-time widening (see EscalationPolicy.night_escalation_bias).
DEFAULT_AMBIGUOUS_BAND = (0.4, 0.75)


@dataclass
class BoundingBox:
    x: float
    y: float
    w: float
    h: float
    t: float  # seconds since event start


def temporal_consistency_score(boxes: list[BoundingBox]) -> float:
    """Returns 0..1: higher = more consistent with a sustained, path-like
    subject (person/vehicle); lower = erratic/small/brief (bird, insect,
    light flicker). Pure geometry, no ML — cheapest possible discriminator.

    TODO: tune thresholds against real event data once camera feeds are
    wired in; these are reasonable starting defaults, not measured.
    """
    if len(boxes) < 2:
        return 0.5  # not enough data to judge either way

    duration = boxes[-1].t - boxes[0].t
    avg_area = sum(b.w * b.h for b in boxes) / len(boxes)

    # Erratic/small/brief -> low score. Sustained/larger -> high score.
    duration_score = min(duration / 2.0, 1.0)  # saturates at 2s+
    size_score = min(avg_area / 0.05, 1.0)  # saturates at 5% of frame area
    return 0.5 * duration_score + 0.5 * size_score


def _classify(snapshot: bytes, camera: CameraProfile) -> tuple[str, float]:
    """Stub for the real re-classification model. TODO: load an ONNX
    model (CPU or CUDA via onnxruntime) and run inference here. Returns
    (label, confidence)."""
    return "unknown", 0.5


def evaluate(
    event: FrigateEvent,
    camera: CameraProfile,
    snapshot: bytes,
    boxes: list[BoundingBox],
    ambiguous_band: tuple[float, float] = DEFAULT_AMBIGUOUS_BAND,
) -> TierResult:
    consistency = temporal_consistency_score(boxes)
    _label, class_confidence = _classify(snapshot, camera)

    # Blend, biased by the camera's trust_bias (WiFi cameras default lower
    # — see docs/architecture.md "Per-camera profiles").
    confidence = (0.6 * consistency + 0.4 * class_confidence) * camera.trust_bias

    low, high = ambiguous_band
    if confidence < low:
        decision = Decision.SUPPRESS
    elif confidence > high:
        decision = Decision.ALARM
    else:
        decision = Decision.AMBIGUOUS

    return TierResult(
        decision=decision,
        confidence=confidence,
        source="tier1",
        reasoning=(
            f"temporal_consistency={consistency:.2f} "
            f"class_confidence={class_confidence:.2f} "
            f"trust_bias={camera.trust_bias:.2f}"
        ),
    )
