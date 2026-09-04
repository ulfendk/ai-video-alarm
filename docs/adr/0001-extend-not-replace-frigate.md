# ADR-0001: Extend Frigate, don't replace it

## Status
Accepted

## Context

The user's complaint is that Frigate over-alarms: it triggers on
motion-then-single-frame-object-match, with no temporal or contextual
reasoning (a bird flying past a bicycle reads as "bicycle detected"). The
backlog asks for a new Docker-based system with Coral + optional cloud AI
analysis, MQTT/HA integration, snapshotting, archive, and a full alarm
layer.

The open question was whether that new system should replace Frigate's
whole pipeline (stream ingestion, recording, first-pass detection) or sit
downstream of it, consuming its output.

## Decision

**Extend Frigate. Build a secondary verification + orchestration layer,
not a replacement.**

## Reasoning

- Frigate already solves the hard, unglamorous problems: RTSP/RTMP
  ingestion per camera, hardware-accelerated decode, continuous recording
  with pre/post-event clip extraction, zones/masks, a snapshot/clip HTTP
  API, and an MQTT event schema HA already understands. Reimplementing any
  slice of this is weeks of work with a high defect surface (RTSP is
  notoriously fiddly across camera firmware).
- The actual complaint — no temporal/contextual reasoning before alarming —
  is precisely a re-classification/verification problem, not an ingestion
  problem.
- Frigate emits exactly the raw material needed for free: MQTT events
  keyed by a stable `event_id`, snapshot JPEGs, and clips.
- Frigate's own zones/masks already give coarse per-zone filtering (the
  literal "cat in the backyard" case can partly be handled there too) —
  building on top of that avoids duplicating zone geometry logic.
- The user confirmed Frigate is already running in production. Replacing
  it would mean re-onboarding all 8 cameras (4 Dahua + 4 WiFi) from
  scratch, discarding a working, tuned setup.

## Consequences

- `alarm-core` depends on Frigate's MQTT event schema and HTTP snapshot/clip
  API remaining stable (both are well-established, low churn).
- The single Coral device stays assigned to Frigate's own primary
  detection (per user confirmation); `alarm-core`'s local re-verification
  tier (Tier 1) runs on the host's CPU/NVIDIA GPU instead — see
  [ADR-0002](0002-python-runtime.md).
- Camera-level changes (adding a camera, adjusting zones) happen in
  Frigate's config as they do today; `alarm-core` only needs to know which
  Frigate camera/zone names to subscribe to.
