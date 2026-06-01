"""Entry point for the Raspberry Pi control server."""

from __future__ import annotations

import logging
import signal
import sys
from pathlib import Path

import uvicorn

from src.camera import CameraStream
from src.config import load_config
from src.pico_link import PicoLink
from src.server import create_app

logger = logging.getLogger(__name__)

_CONFIG_PATH = Path(__file__).resolve().parent.parent / "config.yaml"


def _configure_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )


def main() -> None:
    _configure_logging()
    config = load_config(_CONFIG_PATH)

    assert config.camera is not None
    assert config.serial is not None
    assert config.server is not None
    assert config.safety is not None

    camera = CameraStream(config.camera)
    camera.start()

    pico = PicoLink(config.serial)
    app = create_app(config, camera, pico)

    server_cfg = config.server
    uvicorn_config = uvicorn.Config(
        app,
        host=server_cfg.host,
        port=server_cfg.port,
        log_level="info",
    )
    server = uvicorn.Server(uvicorn_config)

    def _shutdown(signum: int, _frame: object) -> None:
        logger.info("Received signal %s, shutting down", signum)
        server.should_exit = True

    signal.signal(signal.SIGINT, _shutdown)
    signal.signal(signal.SIGTERM, _shutdown)

    try:
        server.run()
    except KeyboardInterrupt:
        logger.info("Interrupted")
    finally:
        logger.info("Cleanup complete")


if __name__ == "__main__":
    main()
    sys.exit(0)
