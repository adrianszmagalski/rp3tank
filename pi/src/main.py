"""Entry point: logging, signal handling, uvicorn."""

from __future__ import annotations

import logging
from pathlib import Path

import uvicorn

from src.config import load_config
from src.server import create_app

logger = logging.getLogger(__name__)

_PI_ROOT = Path(__file__).resolve().parent.parent


def setup_logging(level_name: str) -> None:
    level = getattr(logging, level_name.upper(), logging.INFO)
    logging.basicConfig(
        level=level,
        format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    logging.getLogger("uvicorn.access").setLevel(logging.INFO)


def main() -> None:
    config_path = _PI_ROOT / "config.yaml"
    config = load_config(config_path)
    setup_logging(config.server.log_level)

    app = create_app(config)

    logger.info(
        "Starting server on %s:%d",
        config.server.host,
        config.server.port,
    )
    uvicorn.run(
        app,
        host=config.server.host,
        port=config.server.port,
        log_config=None,
    )


if __name__ == "__main__":
    main()
