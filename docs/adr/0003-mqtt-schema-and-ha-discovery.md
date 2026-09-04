# ADR-0003: MQTT schema and HA MQTT Discovery

## Status
Accepted

## Context

`alarm-core` needs to consume Frigate's existing MQTT events and publish
its own verified-alarm decisions and alarm-panel state in a way Home
Assistant can consume with minimal custom integration work. An existing
Mosquitto broker is already in use by Frigate and HA.

## Decision

- Consume Frigate's existing topics as-is: `frigate/events` (full JSON
  lifecycle: `new`/`update`/`end`, with `id`, `camera`, `label`,
  `sub_label`, `zones`, `top_score`, `has_snapshot`, `has_clip`), and
  per-camera retained snapshot topics where enabled.
- Publish under a new `aivideoalarm/` prefix:
  - `aivideoalarm/<camera>/<zone>/verified_alarm` — retained JSON payload
    (full decision detail: scores, verification source, snapshot/clip
    URLs).
  - `aivideoalarm/<camera>/<zone>/verified_alarm/state` — plain `ON`/`OFF`
    companion topic for a `binary_sensor`.
  - `aivideoalarm/<camera>/doorbell` — doorbell fast-path event.
  - `aivideoalarm/system/alarm_panel/state` /
    `aivideoalarm/system/alarm_panel/set` — mirrors HA's MQTT Alarm Control
    Panel contract exactly (`disarmed`, `armed_home`, `armed_away`,
    `armed_night`, `pending`, `arming`, `disarming`, `triggered`).
  - `aivideoalarm/system/status` — LWT (`online`/`offline`) referenced as
    the `availability` topic on every discovery config.
- Use **HA MQTT Discovery** (`homeassistant/<component>/aivideoalarm_.../config`)
  for all entities: `binary_sensor` per camera/zone, `camera` pointed at
  the latest verified snapshot, `alarm_control_panel` for the system state.

## Reasoning

MQTT Discovery means HA auto-creates entities, dashboards, and automation
triggers work immediately with zero custom integration code — this covers
the large majority of the user's "easy triggers and easy use of photos in
notifications" requirement without committing to building and maintaining
a custom HA integration. A custom integration/add-on-hosted panel (see the
`addon/` scaffold) stays additive UX sugar for later (e.g. a "snooze zone"
service), not a v1 requirement.

## Consequences

- `alarm-core` is a pure MQTT client + HTTP server; no HA-side Python code
  is required for the entities to exist.
- Arm/disarm commands, and the state itself, flow entirely over MQTT — HA
  is a client of alarm-core's state machine, not the other way around.
