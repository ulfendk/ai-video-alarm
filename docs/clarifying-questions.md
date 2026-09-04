# Open items

All architectural decisions are resolved — see the [ADRs](adr/) and
[architecture.md](architecture.md). What's left is deployment-time detail,
needed to move from the scaffold to a running system, not further design
choices:

1. **Per-camera Frigate names/RTSP identifiers** for the 8 cameras (4
   Dahua, 4 WiFi), and which Frigate zone name(s) each maps to — needed to
   fill in `config/alarm-core.example.yaml` for real.
2. **Door/window contact-sensor entity IDs** in HA, for the ones you said
   are usable for forced-entry correlation.
3. **Frigate's base URL** reachable from wherever `alarm-core` runs (e.g.
   `http://frigate.local:5000`).
4. **MQTT broker connection details** (host/port/credentials) for the
   existing Mosquitto instance.
5. **Anthropic API key** for the Claude vision Tier-2 calls (kept out of
   git — goes in `.env`, never committed).
6. **VPN/reverse-proxy hostname** to use as the base URL for media served
   into HA mobile push notifications.
7. **Archive volume path** on the host (same host as Frigate's own
   recordings, per your answer) — the actual mount point to bind into the
   `alarm-core` container.

None of these block the current scaffold — they're all `# TODO` /
placeholder fields in the compose file and example config, to be filled in
when wiring this up to the live HA instance.

## Note on door/window correlation (item 2)

The wiring assumes your HA instance forwards entity state changes to MQTT
under `<base_topic>/<domain>/<object_id>/state` (HA's "MQTT statestream"
integration's default layout, `base_topic` defaults to `homeassistant` —
configurable via `HA_STATESTREAM_BASE_TOPIC` in `.env` if you use
something else, e.g. a different bridge or a custom base topic). If you
don't already have MQTT statestream (or equivalent) enabled, that's an
extra HA-side integration to turn on, not something `alarm-core` can
substitute for — worth confirming when you get to deployment.
