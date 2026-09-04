"""FastAPI app: health check, static media mount (serves the archive for
HA rich-push notifications and the HA add-on's ingress panel), and a
minimal panel API for the add-on to proxy. See docs/architecture.md.
"""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from aivideoalarm.alarm_state import AlarmStateMachine
from aivideoalarm.config import Settings


def create_app(settings: Settings, alarm_state: AlarmStateMachine) -> FastAPI:
    app = FastAPI(title="ai-video-alarm alarm-core")

    @app.get("/health")
    def health() -> dict:
        return {"status": "ok"}

    @app.get("/api/alarm_state")
    def get_alarm_state() -> dict:
        return {"state": alarm_state.state.value}

    archive_root = settings.archive_path
    archive_root.mkdir(parents=True, exist_ok=True)
    app.mount("/media", StaticFiles(directory=str(archive_root)), name="media")

    return app
