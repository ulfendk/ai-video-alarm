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
- [`docs/deployment/portainer.md`](docs/deployment/portainer.md) —
  running `alarm-core` on a Docker/Portainer host, pulling the published
  image from GHCR.

## Layout

```
services/alarm-core/   Python service: the verification pipeline, MQTT
                        client, archive, alarm state machine.
addon/                  Thin Home Assistant add-on — ingress panel/proxy
                        only, runs no workload.
config/                 User-tunable config (cameras, zones, rules).
docker-compose.yml       Production/Portainer compose file — pulls the
                        image from GHCR, no build context needed.
docker-compose.override.yml  Local-dev-only: adds a build from source,
                        auto-loaded by `docker compose up` in this repo.
```

## Image

`services/alarm-core` publishes to
[`ghcr.io/ulfendk/ai-video-alarm-core`](https://github.com/ulfendk/ai-video-alarm/pkgs/container/ai-video-alarm-core)
via `.github/workflows/docker-publish.yml`. See
[`docs/deployment/portainer.md`](docs/deployment/portainer.md) for how to
run it.

## Status

Initial architecture + scaffold. Not yet wired to a live deployment — see
`docs/clarifying-questions.md`.
