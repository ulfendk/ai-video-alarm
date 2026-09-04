# ai-video-alarm

A smart verification and alarm-orchestration layer that sits on top of an
existing [Frigate](https://frigate.video) NVR setup, to cut down false
alarms and turn Home Assistant into a proper alarm system.

Frigate is great at motion/object detection but has no contextual
reasoning — a bird flying past a bicycle reads as "bicycle detected."
This project consumes Frigate's MQTT events and snapshots, re-verifies
them locally, escalates genuinely ambiguous high-stakes cases to Claude
vision, applies zone/time-aware suppression rules (the literal
"neighbour's cat" case), and publishes a much more trustworthy set of
alarm entities back to Home Assistant over MQTT.

## Start here

- [`docs/architecture.md`](docs/architecture.md) — full design, component
  diagram, data flow.
- [`docs/adr/`](docs/adr/) — the key decisions and why (extend Frigate
  rather than replace it, Python runtime, MQTT schema, archive design).
- [`docs/clarifying-questions.md`](docs/clarifying-questions.md) — what's
  still needed (real camera/zone names, entity IDs, credentials) before
  this scaffold becomes a running deployment.

## Layout

```
services/alarm-core/   Python service: the verification pipeline, MQTT
                        client, archive, alarm state machine.
addon/                  Thin Home Assistant add-on — ingress panel/proxy
                        only, runs no workload.
config/                 User-tunable config (cameras, zones, rules).
docker-compose.yml       Compose stack for the alarm-core side (Frigate
                        itself is assumed already running).
```

## Status

Initial architecture + scaffold. Not yet wired to a live deployment — see
`docs/clarifying-questions.md`.
