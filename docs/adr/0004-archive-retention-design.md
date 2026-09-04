# ADR-0004: Archive storage and quota-based retention

## Status
Accepted

## Context

The user wants an archive of relevant photos/videos to browse later,
quota'd so the oldest content is pruned first as usage approaches the
limit. Default target size: 20-50GB, on the same host as Frigate's own
recordings (configurable).

## Decision

- Filesystem layout:
  ```
  archive/<camera>/<yyyy>/<mm>/<dd>/<event_id>_<timestamp>_<label>.jpg
  archive/<camera>/<yyyy>/<mm>/<dd>/<event_id>_<timestamp>_<label>.mp4   (if verified as alarm-worthy and Frigate has a clip)
  archive/<camera>/<yyyy>/<mm>/<dd>/<event_id>_<timestamp>_<label>.meta.json (decision trail: tier scores, rule fired, cloud verdict/reasoning)
  ```
- Only verified (alarm or otherwise notable) events get archived long-term.
  Pure suppressions can optionally be kept briefly (24-48h) in a separate,
  more aggressively-pruned staging area for audit/debugging, not counted
  against the main quota.
- All metadata indexed in SQLite (`alarm-db`); the filesystem is blob
  storage only — listing/search/pruning decisions query the DB.
- Quota enforcement: a periodic job sums current size from the DB index;
  once usage crosses a high watermark (e.g. 90% of `archive_quota_gb`),
  delete oldest-first (by timestamp) until back under a lower watermark
  (e.g. 80%) — hysteresis avoids thrashing at the boundary.
- A "kept/starred" bucket (user-flagged, e.g. via a notification action
  button or the add-on panel) is excluded from automatic pruning.
- `archive_quota_gb` is a config value, default 30 (within the user's
  20-50GB target range), user-adjustable per deployment.

## Consequences

- SQLite is sufficient at this scale (single-writer, simplifies ops); no
  Postgres dependency for v1.
- Clip storage dominates size vs. snapshots — a config option restricts
  clip archiving to `alarm` decisions only (not ambiguous-but-suppressed),
  to control growth, while snapshots are always kept for anything
  archived.
- Media is served for HA rich push via `alarm-core`'s FastAPI static mount
  over the user's existing VPN/reverse proxy; IM/email default to direct
  file-attach via a shared mount path where the notification integration
  supports it, avoiding a hard dependency on external reachability.
