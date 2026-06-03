"""Configuration loading from YAML with dataclass defaults."""

from __future__ import annotations

import logging
from dataclasses import dataclass, fields
from pathlib import Path
from typing import Any, TypeVar

import yaml

logger = logging.getLogger(__name__)

T = TypeVar("T")


@dataclass
class CameraConfig:
    width: int = 960
    height: int = 540
    fps: int = 30
    quality: str = "HIGH"


@dataclass
class SerialConfig:
    port: str = "/dev/serial0"
    baud: int = 115200
    reconnect_seconds: float = 2.0


@dataclass
class ServerConfig:
    host: str = "0.0.0.0"
    port: int = 8000
    log_level: str = "INFO"


@dataclass
class SafetyConfig:
    control_timeout_ms: int = 500
    pan_min: int = 10
    pan_max: int = 170
    tilt_min: int = 30
    tilt_max: int = 150


@dataclass
class DiagnosticsConfig:
    pico_stale_ms: int = 1000


@dataclass
class AppConfig:
    camera: CameraConfig
    serial: SerialConfig
    server: ServerConfig
    safety: SafetyConfig
    diagnostics: DiagnosticsConfig

    @classmethod
    def defaults(cls) -> AppConfig:
        return cls(
            camera=CameraConfig(),
            serial=SerialConfig(),
            server=ServerConfig(),
            safety=SafetyConfig(),
            diagnostics=DiagnosticsConfig(),
        )


def clamp(value: int | float, lo: int | float, hi: int | float) -> int:
    return int(max(lo, min(hi, value)))


def _merge_dataclass(instance: T, data: dict[str, Any] | None) -> T:
    if not data:
        return instance
    valid = {f.name for f in fields(instance)}  # type: ignore[arg-type]
    for key, value in data.items():
        if key in valid and value is not None:
            setattr(instance, key, value)
    return instance


def load_config(path: Path | None = None) -> AppConfig:
    """Load YAML config; missing file or keys fall back to dataclass defaults."""
    cfg = AppConfig.defaults()
    if path is None:
        path = Path("config.yaml")

    if not path.is_file():
        logger.info("Config file not found at %s, using defaults", path)
        return cfg

    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        logger.warning("Invalid YAML in %s: %s — using defaults", path, exc)
        return cfg
    except OSError as exc:
        logger.warning("Cannot read %s: %s — using defaults", path, exc)
        return cfg

    if not isinstance(raw, dict):
        logger.warning("Config root is not a mapping — using defaults")
        return cfg

    _merge_dataclass(cfg.camera, raw.get("camera"))
    _merge_dataclass(cfg.serial, raw.get("serial"))
    _merge_dataclass(cfg.server, raw.get("server"))
    _merge_dataclass(cfg.safety, raw.get("safety"))
    _merge_dataclass(cfg.diagnostics, raw.get("diagnostics"))
    return cfg


def parse_mjpeg_quality(name: str) -> Any:
    """Map config quality string to picamera2.encoders.Quality."""
    try:
        from picamera2.encoders import Quality
    except ImportError:
        logger.debug("Picamera2 not available for quality parsing")
        return None

    key = str(name).strip().upper()
    table = {
        "VERY_LOW": Quality.VERY_LOW,
        "LOW": Quality.LOW,
        "MEDIUM": Quality.MEDIUM,
        "HIGH": Quality.HIGH,
        "VERY_HIGH": Quality.VERY_HIGH,
    }
    if key not in table:
        logger.warning("Unknown MJPEG quality %r, using HIGH", name)
        return Quality.HIGH
    return table[key]
