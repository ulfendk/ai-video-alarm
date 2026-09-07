"""Configuration: environment-derived secrets/connection settings (Settings)
and the user-tunable YAML config (AppConfig) — cameras, zones, suppression
rules, escalation policy.

Keeping these separate mirrors config/alarm-core.example.yaml (safe to
commit, no secrets) vs. .env (gitignored, real secrets/hostnames).
"""

from __future__ import annotations

from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Environment-derived settings — connection details and secrets.

    Populated from process environment / .env, per docker-compose.yml.
    """

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    frigate_url: str = "http://frigate.local:5000"
    mqtt_host: str = "mosquitto.local"
    mqtt_port: int = 1883
    mqtt_username: str = ""
    mqtt_password: str = ""

    anthropic_api_key: str = ""

    archive_quota_gb: float = 30.0
    archive_path: Path = Path("/data/archive")
    db_path: Path = Path("/data/db/alarm-core.sqlite3")

    cloud_ai_daily_call_cap: int = 20

    public_media_base_url: str = ""

    # Topic base HA's "MQTT statestream" integration publishes entity
    # states to (HA's own default is "homeassistant" — same prefix as our
    # Discovery configs, but under <domain>/<object_id>/state rather than
    # <component>/<object_id>/config, so there's no collision). Change
    # this if your bridge uses a different convention.
    ha_statestream_base_topic: str = "homeassistant"

    config_path: Path = Path("/config/alarm-core.yaml")

    api_host: str = "0.0.0.0"
    api_port: int = 8090


class CameraProfile(BaseModel):
    """Per-camera config. Dahua and cheap WiFi cameras are not equivalent —
    see docs/architecture.md "Per-camera profiles"."""

    name: str
    frigate_camera: str
    zones: list[str] = Field(default_factory=list)
    kind: Literal["dahua_low_light", "wifi_generic"] = "wifi_generic"
    # Cheap WiFi cameras generally warrant a lower baseline trust in Tier 1
    # (noisier sensors, weaker low-light handling) than the Dahua units.
    trust_bias: float = 1.0
    is_doorbell: bool = False


class ZoneRule(BaseModel):
    """One row of the zone+label+time-window suppression matrix (the "cat
    in the backyard" case, generalized). Evaluated in order; first match
    wins."""

    camera: str  # camera `name`, or "*" for any
    zone: str  # zone name, or "*" for any
    label: str  # e.g. "cat", "bird", "person", or "*" for any
    decision: Literal["suppress", "alarm", "escalate"]
    alarm_states: list[str] = Field(
        default_factory=lambda: ["armed_home", "armed_away", "armed_night"]
    )
    time_window: str | None = None  # e.g. "07:00-09:00", None = all day


class DoorWindowSensor(BaseModel):
    """A door/window contact sensor entity in HA, usable for forced-entry
    correlation alongside camera events."""

    entity_id: str
    label: str  # human-readable, e.g. "front door"
    camera: str | None = None  # associated camera `name`, if any


class EscalationPolicy(BaseModel):
    tier1_ambiguous_confidence_band: tuple[float, float] = (0.4, 0.75)
    sensitive_zones: list[str] = Field(default_factory=list)
    night_escalation_bias: float = 0.15  # widens the ambiguous band at night
    debounce_seconds: int = 60
    # Simple clock-hour night window (local time), used to bias Tier-1/2
    # escalation per docs/architecture.md "Low-light handling strategy".
    # A sun-elevation-based (civil twilight) switch would be more precise
    # but needs HA to publish sun.sun over MQTT statestream; these are a
    # deployment-agnostic fallback, override per-season if needed.
    night_start_hour: int = 20
    night_end_hour: int = 7


class AppConfig(BaseModel):
    """The user-tunable config loaded from config/alarm-core.yaml."""

    cameras: list[CameraProfile] = Field(default_factory=list)
    zone_rules: list[ZoneRule] = Field(default_factory=list)
    door_window_sensors: list[DoorWindowSensor] = Field(default_factory=list)
    escalation: EscalationPolicy = Field(default_factory=EscalationPolicy)

    @classmethod
    def load(cls, path: Path) -> AppConfig:
        data = yaml.safe_load(path.read_text()) if path.exists() else {}
        return cls.model_validate(data or {})


def load_settings() -> Settings:
    return Settings()


def load_app_config(settings: Settings) -> AppConfig:
    return AppConfig.load(settings.config_path)
