# AI Video Alarm Panel (Home Assistant add-on)

Thin ingress panel/reverse-proxy into the `alarm-core` service, which runs
on separate hardware (the NVR/AI host, alongside Frigate). This add-on
does **not** run Frigate, inference, or archive storage — see
[`docs/architecture.md`](../docs/architecture.md) in the repo root for why.

## What it does

- Reverse-proxies HA's Ingress into `alarm-core`'s web UI/API, so the
  archive/status panel shows up in the HA sidebar without exposing a
  separate port.

## Configuration

- `alarm_core_url`: base URL of `alarm-core` on the NVR/AI host, e.g.
  `http://192.168.1.50:8090`.
- `auth_token`: bearer token for `alarm-core`'s API, if configured.

## Status

Scaffold only — the entities themselves (alarm panel, per-camera verified
alarm sensors, snapshot camera) come from `alarm-core`'s MQTT Discovery
publishing (see
[`docs/adr/0003-mqtt-schema-and-ha-discovery.md`](../docs/adr/0003-mqtt-schema-and-ha-discovery.md)),
not from this add-on. This add-on is purely the optional UI convenience
layer.
