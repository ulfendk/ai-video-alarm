"""Writes verified events to the archive filesystem layout and indexes
them in SQLite. Layout: docs/adr/0004-archive-retention-design.md.
"""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from pathlib import Path

from aivideoalarm.pipeline.types import Decision, VerificationOutcome

SCHEMA = """
CREATE TABLE IF NOT EXISTS archive_events (
    event_id TEXT PRIMARY KEY,
    camera TEXT NOT NULL,
    label TEXT NOT NULL,
    decision TEXT NOT NULL,
    verification_source TEXT NOT NULL,
    confidence REAL NOT NULL,
    rule_fired TEXT,
    reasoning TEXT,
    snapshot_path TEXT,
    clip_path TEXT,
    size_bytes INTEGER NOT NULL DEFAULT 0,
    kept INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_archive_events_created_at ON archive_events(created_at);
"""


class ArchiveWriter:
    def __init__(self, archive_root: Path, db_path: Path) -> None:
        self._archive_root = archive_root
        self._db_path = db_path
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._archive_root.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _init_db(self) -> None:
        with sqlite3.connect(self._db_path) as conn:
            conn.executescript(SCHEMA)

    def _event_dir(self, camera: str, when: datetime) -> Path:
        d = self._archive_root / camera / f"{when:%Y}" / f"{when:%m}" / f"{when:%d}"
        d.mkdir(parents=True, exist_ok=True)
        return d

    def write(
        self,
        outcome: VerificationOutcome,
        snapshot_bytes: bytes | None,
        clip_bytes: bytes | None,
    ) -> None:
        """Only ALARM (and, per ADR-0004, optionally kept-ambiguous)
        outcomes should reach here — the caller decides what's worth
        archiving long-term vs. the short-lived raw staging area."""
        now = datetime.now()
        event_dir = self._event_dir(outcome.event.camera, now)
        stem = f"{outcome.event.event_id}_{now:%Y%m%dT%H%M%S}_{outcome.event.label}"

        snapshot_path = None
        clip_path = None
        size_bytes = 0

        if snapshot_bytes is not None:
            snapshot_path = event_dir / f"{stem}.jpg"
            snapshot_path.write_bytes(snapshot_bytes)
            size_bytes += len(snapshot_bytes)

        # Clips only for confirmed ALARM decisions, per ADR-0004 (clip
        # storage dominates size).
        if clip_bytes is not None and outcome.decision == Decision.ALARM:
            clip_path = event_dir / f"{stem}.mp4"
            clip_path.write_bytes(clip_bytes)
            size_bytes += len(clip_bytes)

        meta_path = event_dir / f"{stem}.meta.json"
        meta = {
            "event_id": outcome.event.event_id,
            "camera": outcome.event.camera,
            "label": outcome.event.label,
            "decision": outcome.decision.value,
            "verification_source": outcome.verification_source,
            "confidence": outcome.confidence,
            "rule_fired": outcome.rule_fired,
            "reasoning": outcome.reasoning,
            "created_at": now.isoformat(),
        }
        meta_path.write_text(json.dumps(meta, indent=2))
        size_bytes += len(meta_path.read_bytes())

        with sqlite3.connect(self._db_path) as conn:
            conn.execute(
                """INSERT OR REPLACE INTO archive_events
                (event_id, camera, label, decision, verification_source, confidence,
                 rule_fired, reasoning, snapshot_path, clip_path, size_bytes, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    outcome.event.event_id,
                    outcome.event.camera,
                    outcome.event.label,
                    outcome.decision.value,
                    outcome.verification_source,
                    outcome.confidence,
                    outcome.rule_fired,
                    outcome.reasoning,
                    str(snapshot_path) if snapshot_path else None,
                    str(clip_path) if clip_path else None,
                    size_bytes,
                    now.isoformat(),
                ),
            )
