# Architecture

## Problem

Frigate NVR detects motion, then classifies whatever object is in the motion
region. It has no sense of *plausibility* — a bird flying past a bicycle in
the frame reads as "a bicycle was detected." That single-frame,
context-free decision is the source of most false alarms in the current
setup.

This project does not replace Frigate. It sits downstream of it as a
**verification and orchestration layer**: Frigate keeps doing what it's
good at (stream ingestion, hardware-accelerated decode, recording, zones,
first-pass detection), and `alarm-core` decides whether a Frigate event is
actually worth alarming on, using local re-classification, temporal
reasoning, contextual suppression rules, and — only when genuinely
ambiguous and high-stakes — a cloud vision call.

See [ADR-0001](adr/0001-extend-not-replace-frigate.md) for the full
reasoning.

## Components

```
                    ┌─────────────┐
  8 cameras ───────▶│   Frigate   │  (existing, already running)
 (4 Dahua,           │  ingest/    │
  4 WiFi)            │  record/    │
                    │  detect/    │
                    │  zones      │
                    └──────┬──────┘
                           │ MQTT (frigate/events, snapshot topics)
                           │ HTTP (snapshot/clip API)
                           ▼
                    ┌─────────────────────────────────────────┐
                    │              alarm-core                  │
                    │                                          │
                    │  MQTT client ── Frigate HTTP client       │
                    │        │                                 │
                    │        ▼                                 │
                    │  Tier 0: zone/mask filter (Frigate's own) │
                    │        │                                 │
                    │        ▼                                 │
                    │  Tier 1: local re-classification +        │
                    │          temporal consistency check       │
                    │          (CPU/CUDA on the i7+NVIDIA host, │
                    │           the Coral stays with Frigate)   │
                    │        │                                 │
                    │        ▼ (only if ambiguous + high-stakes)│
                    │  Tier 2: Claude vision call                │
                    │          (rate-limited to a small daily    │
                    │           cap — minimal budget)            │
                    │        │                                 │
                    │        ▼                                 │
                    │  Suppression rules (zone/label/time-window,│
                    │  home/away/night gating, door/window       │
                    │  contact-sensor correlation)                │
                    │        │                                 │
                    │        ▼                                 │
                    │  Alarm state machine                       │
                    │  (disarmed/armed_home/armed_away/          │
                    │   armed_night — authoritative)             │
                    │        │                                 │
                    │        ▼                                 │
                    │  Archive writer + quota pruner              │
                    │  (SQLite index, filesystem blobs,           │
                    │   default 20-50GB, oldest-first prune)      │
                    │        │                                 │
                    │        ▼                                 │
                    │  FastAPI (health, static media, minimal    │
                    │  panel API for the HA add-on to proxy)     │
                    └──────────────┬──────────────────────────┘
                                   │ MQTT (aivideoalarm/... + HA
                                   │       MQTT Discovery configs)
                                   ▼
                    ┌─────────────────────────────────────────┐
                    │           Home Assistant                 │
                    │  - binary_sensor / camera / alarm_control_ │
                    │    panel entities (via MQTT Discovery)    │
                    │  - automations: notify.mobile_app_* push, │
                    │    notify.smtp email, lock service calls, │
                    │    presence-simulation start/stop         │
                    │  - "AI Video Alarm" add-on: thin ingress   │
                    │    panel/reverse-proxy to alarm-core's     │
                    │    web UI (no workload here)               │
                    └─────────────────────────────────────────┘
```

## Data flow — typical event

1. Camera motion → Frigate detects + classifies → publishes to
   `frigate/events` (MQTT) with a stable `event_id`.
2. `alarm-core` receives the event, fetches the snapshot (and a short frame
   burst if a clip is available) via Frigate's HTTP API.
3. Tier 0: is the event even in a zone/label combo we care about? (Mostly
   handled by Frigate's own zone/mask config already.)
4. Tier 1: re-classify locally + check trajectory/motion-pattern
   consistency across frames. Small, erratic motion (bird) vs. larger,
   sustained, path-like motion (person) is a strong, cheap signal. Produces
   `suppress` / `alarm` / `ambiguous`.
5. If `ambiguous` **and** stakes are high (armed_away/armed_night, or a
   sensitive zone like the front porch) → Tier 2: send 1-3 frames + a
   structured context prompt (camera, zone, current arm state, time of day,
   recent suppression history) to Claude vision, get back a structured
   verdict + reasoning. Rate-limited to a small daily cap to match the
   minimal cloud budget; degrades gracefully to Tier-1-only once exceeded.
6. Suppression rules apply on top (zone+label+time-window matrix, debounce,
   door/window sensor correlation for forced-entry signals).
7. Final decision → publish MQTT verified-alarm entity (retained JSON +
   plain state topic) → HA picks it up via MQTT Discovery → HA automations
   handle notification delivery and lock/presence-simulation side effects.
8. Archive: snapshot/clip + full decision trail written to
   `archive/<camera>/<yyyy>/<mm>/<dd>/`, indexed in SQLite. A background
   pruner keeps total size under the configured quota, oldest-first, with a
   hysteresis band, and skips anything the user has starred/kept.

## Doorbell fast path

A doorbell trigger bypasses the verification pipeline entirely: `alarm-core`
pulls a fresh snapshot directly from the camera's own snapshot endpoint
(low-latency, "who's there right now") and publishes a `doorbell` event
straight through, no Tier 1/2 involved.

## Per-camera profiles

The 4 Dahua and 4 WiFi cameras are not equivalent — Dahua cameras have
useful color low-light capability; the cheap WiFi cameras likely don't and
should carry looser default confidence/trust settings. This is a per-camera
config field (`config/alarm-core.example.yaml`), not a hardcoded assumption.

## What alarm-core does *not* own

- **Lock actuation** — stays in HA automations (locks are already
  HA-integrated; alarm-core stays brand-agnostic and just publishes its
  arm/disarm state for automations to react to).
- **Presence detection** — the arm/disarm state itself *is* the presence
  signal in this setup (that's how presence simulation is driven today), so
  alarm-core's own state machine doubles as the "are we away" context
  without a separate presence integration.
- **Notification delivery** — HA automations call `notify.mobile_app_*` /
  `notify.smtp`, triggered off alarm-core's MQTT entities. alarm-core's job
  is only to make the event + reachable media available.
