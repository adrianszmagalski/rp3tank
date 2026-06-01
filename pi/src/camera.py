"""Picamera2 hardware MJPEG stream with latest-frame buffer."""

from __future__ import annotations

import logging
import threading
from typing import Iterator

from src.config import CameraConfig

logger = logging.getLogger(__name__)

try:
    from picamera2 import Picamera2
    from picamera2.encoders import MJPEGEncoder
    from picamera2.outputs import Output

    _PICAMERA2_AVAILABLE = True
except ImportError:
    Picamera2 = None  # type: ignore[misc, assignment]
    MJPEGEncoder = None  # type: ignore[misc, assignment]
    Output = object  # type: ignore[misc, assignment]
    _PICAMERA2_AVAILABLE = False


class _FrameOutput(Output if _PICAMERA2_AVAILABLE else object):  # type: ignore[misc]
    """Captures encoded JPEG frames from the hardware encoder."""

    def __init__(self, stream: CameraStream) -> None:
        if _PICAMERA2_AVAILABLE:
            super().__init__()
        self._stream = stream

    def write(self, buf: bytes) -> int | None:
        self._stream._on_frame(buf)
        return len(buf) if _PICAMERA2_AVAILABLE else None


class CameraStream:
    """Hardware MJPEG capture; exposes latest frame via threading.Condition."""

    def __init__(self, config: CameraConfig) -> None:
        self._config = config
        self._picam2: Picamera2 | None = None
        self._frame: bytes | None = None
        self._condition = threading.Condition()
        self._running = False
        self._available = _PICAMERA2_AVAILABLE

    @property
    def available(self) -> bool:
        return self._available and self._running

    def start(self) -> None:
        if not _PICAMERA2_AVAILABLE:
            logger.error(
                "Picamera2 not available; camera stream disabled. "
                "Install system package and use venv --system-site-packages."
            )
            return

        cfg = self._config
        try:
            picam2 = Picamera2()
            video_config = picam2.create_video_configuration(
                main={"size": (cfg.width, cfg.height)},
                controls={"FrameRate": cfg.fps},
            )
            picam2.configure(video_config)
            encoder = MJPEGEncoder(qfactor=cfg.quality)
            output = _FrameOutput(self)
            picam2.start_recording(encoder, output)
            self._picam2 = picam2
            self._running = True
            logger.info(
                "Camera started %dx%d @ %d fps, quality=%d",
                cfg.width,
                cfg.height,
                cfg.fps,
                cfg.quality,
            )
        except Exception as exc:
            logger.error("Failed to start camera: %s", exc)
            self._running = False
            if self._picam2 is not None:
                try:
                    self._picam2.close()
                except Exception:
                    pass
                self._picam2 = None

    def stop(self) -> None:
        if self._picam2 is not None:
            try:
                self._picam2.stop_recording()
            except Exception as exc:
                logger.debug("stop_recording: %s", exc)
            try:
                self._picam2.close()
            except Exception as exc:
                logger.debug("close camera: %s", exc)
            self._picam2 = None
        with self._condition:
            self._frame = None
            self._condition.notify_all()
        self._running = False
        logger.info("Camera stopped")

    def _on_frame(self, buf: bytes) -> None:
        with self._condition:
            self._frame = buf
            self._condition.notify_all()

    def wait_frame(self, timeout: float = 1.0) -> bytes | None:
        """Block until a new frame is available (call from worker thread)."""
        with self._condition:
            if self._frame is None:
                self._condition.wait(timeout=timeout)
            return self._frame

    def frame_generator(self) -> Iterator[bytes]:
        """Yield JPEG frames forever (sync generator for StreamingResponse)."""
        last: bytes | None = None
        while self._running:
            frame = self.wait_frame(timeout=1.0)
            if frame is None:
                continue
            if frame is last:
                continue
            last = frame
            yield frame
