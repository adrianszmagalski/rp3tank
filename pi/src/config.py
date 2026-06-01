"""Configuration loading from YAML with dataclass defaults."""

from __future__ import annotations

import logging
from dataclasses import dataclass, fields
from pathlib import Path
from typing import Any

import yaml

logger = logging.getLogger(__name__)


@dataclass
class CameraConfig:
    width: int = 1280
    height: int = 720
    fps: int = 15
    quality: int = 80


@dataclass
class SerialConfig:
    port: str = "/dev/serial0"
    baud: int = 115200
    reconnect_seconds: float = 3.0


@dataclass
class ServerConfig:
    host: str = "0.0.0.0"
    port: int = 8000


@dataclass
class SafetyConfig:
    control_timeout_ms: int = 500
    pan_min: int = 10
    pan_max: int = 170
    tilt_min: int = 30
    tilt_max: int = 150


@dataclass
class AppConfig:
    camera: CameraConfig | None = None
    serial: SerialConfig | None = None
    server: ServerConfig | None = None
    safety: SafetyConfig | None = None

    def __post_init__(self) -> None:
        if self.camera is None:
            self.camera = CameraConfig()
        if self.serial is None:
            self.serial = SerialConfig()
        if self.server is None:
            self.server = ServerConfig()
        if self.safety is None:
            self.safety = SafetyConfig()


def _dataclass_from_dict(cls: type, data: dict[str, Any] | None) -> Any:
    if not data:
        return cls()
    valid = {f.name for f in fields(cls)}
    filtered = {k: v for k, v in data.items() if k in valid}
    defaults = cls()
    merged = {f.name: getattr(defaults, f.name) for f in fields(cls)}
    merged.update(filtered)
    return cls(**merged)


def load_config(path: Path | None = None) -> AppConfig:
    """Load application config from YAML, falling back to defaults."""
    if path is None:
        path = Path(__file__).resolve().parent.parent / "config.yaml"

    defaults = AppConfig()

    if not path.is_file():
        logger.warning("Config file not found at %s, using defaults", path)
        return defaults

    try:
        with path.open(encoding="utf-8") as fh:
            raw = yaml.safe_load(fh)
    except OSError as exc:
        logger.warning("Failed to read config %s: %s, using defaults", path, exc)
        return defaults
    except yaml.YAMLError as exc:
        logger.warning("Invalid YAML in %s: %s, using defaults", path, exc)
        return defaults

    if not isinstance(raw, dict):
        logger.warning("Config root is not a mapping, using defaults")
        return defaults

    return AppConfig(
        camera=_dataclass_from_dict(CameraConfig, raw.get("camera")),
        serial=_dataclass_from_dict(SerialConfig, raw.get("serial")),
        server=_dataclass_from_dict(ServerConfig, raw.get("server")),
        safety=_dataclass_from_dict(SafetyConfig, raw.get("safety")),
    )


def clamp(value: int, low: int, high: int) -> int:
    return max(low, min(high, value))
