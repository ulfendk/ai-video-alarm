"""HTTP client for Frigate's snapshot/clip API.

alarm-core never touches camera RTSP streams directly — Frigate already
owns ingestion/recording (docs/adr/0001-extend-not-replace-frigate.md).
This client just pulls the media Frigate already captured for a given
event.
"""

from __future__ import annotations

import httpx


class FrigateClient:
    def __init__(self, base_url: str, timeout: float = 10.0) -> None:
        self._client = httpx.AsyncClient(base_url=base_url, timeout=timeout)

    async def get_snapshot(self, event_id: str) -> bytes:
        resp = await self._client.get(f"/api/events/{event_id}/snapshot.jpg")
        resp.raise_for_status()
        return resp.content

    async def get_clip(self, event_id: str) -> bytes:
        resp = await self._client.get(f"/api/events/{event_id}/clip.mp4")
        resp.raise_for_status()
        return resp.content

    async def get_camera_latest_snapshot(self, camera: str) -> bytes:
        """Doorbell fast path: current frame, not tied to a Frigate event."""
        resp = await self._client.get(f"/api/{camera}/latest.jpg")
        resp.raise_for_status()
        return resp.content

    async def aclose(self) -> None:
        await self._client.aclose()
