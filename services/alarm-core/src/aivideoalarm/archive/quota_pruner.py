"""Quota-based oldest-first pruning, with hysteresis to avoid thrashing at
the boundary. See docs/adr/0004-archive-retention-design.md.
"""

from __future__ import annotations

import logging
import sqlite3
from pathlib import Path

logger = logging.getLogger(__name__)

HIGH_WATERMARK_PCT = 0.90
LOW_WATERMARK_PCT = 0.80


class QuotaPruner:
    def __init__(self, db_path: Path, quota_gb: float) -> None:
        self._db_path = db_path
        self._quota_bytes = quota_gb * (1024**3)

    def _current_usage(self, conn: sqlite3.Connection) -> int:
        row = conn.execute(
            "SELECT COALESCE(SUM(size_bytes), 0) FROM archive_events WHERE kept = 0"
        ).fetchone()
        return int(row[0])

    def prune_if_needed(self) -> int:
        """Returns the number of events deleted."""
        deleted = 0
        with sqlite3.connect(self._db_path) as conn:
            usage = self._current_usage(conn)
            if usage < self._quota_bytes * HIGH_WATERMARK_PCT:
                return 0

            low_watermark = self._quota_bytes * LOW_WATERMARK_PCT
            logger.info(
                "Archive usage %.1fGB exceeds high watermark, pruning to %.1fGB",
                usage / 1024**3,
                low_watermark / 1024**3,
            )

            rows = conn.execute(
                """SELECT event_id, snapshot_path, clip_path, size_bytes
                   FROM archive_events WHERE kept = 0 ORDER BY created_at ASC"""
            ).fetchall()

            for event_id, snapshot_path, clip_path, size_bytes in rows:
                if usage <= low_watermark:
                    break
                for path_str in (snapshot_path, clip_path):
                    if path_str:
                        path = Path(path_str)
                        path.unlink(missing_ok=True)
                        meta_path = path.with_suffix("").with_suffix(".meta.json")
                        meta_path.unlink(missing_ok=True)
                conn.execute("DELETE FROM archive_events WHERE event_id = ?", (event_id,))
                usage -= size_bytes
                deleted += 1

        return deleted
