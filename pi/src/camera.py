"""Picamera2 hardware MJPEG stream with latest-frame buffer."""

from __future__ import annotations

import asyncio
import io
import logging
import threading
from collections.abc import AsyncIterator, Iterator
from typing import TYPE_CHECKING

from src.config import CameraConfig, parse_mjpeg_quality

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from picamera2 import Picamera2

_PICAMERA2_AVAILABLE = False
Picamera2_cls: type | None = None
MJPEGEncoder_cls: type | None = None
FileOutput_cls: type | None = None

try:
    from picamera2 import Picamera2 as Picamera2_cls  # type: ignore[no-redef]
    from picamera2.encoders import MJPEGEncoder as MJPEGEncoder_cls  # type: ignore[no-redef]
    from picamera2.outputs import FileOutput as FileOutput_cls  # type: ignore[no-redef]

    _PICAMERA2_AVAILABLE = True
except ImportError:
    pass


class StreamingOutput(io.BufferedIOBase):
    """Receives JPEG frames from hardware MJPEG encoder via FileOutput.write()."""

    def __init__(self) -> None:
        self._frame: bytes | None = None
        self._condition = threading.Condition()

    def writable(self) -> bool:
        return True

    def write(self, buf: bytes) -> int:
        with self._condition:
            self._frame = buf
            self._condition.notify_all()
        return len(buf)

    def wait_for_new_frame(self, last: bytes | None, timeout: float) -> bytes | None:
        with self._condition:
            self._condition.wait(timeout=timeout)
            frame = self._frame
            if frame is None or frame is last:
                return None
            return frame


def format_mjpeg_part(frame: bytes) -> bytes:
    header = (
        b"--frame\r\n"
        b"Content-Type: image/jpeg\r\n"
        + f"Content-Length: {len(frame)}\r\n\r\n".encode()
    )
    return header + frame + b"\r\n"


class CameraStream:
    """Hardware MJPEG camera stream for multipart HTTP responses."""

    def __init__(self, config: CameraConfig) -> None:
        self._config = config
        self._picam2: Picamera2 | None = None
        self._output = StreamingOutput()
        self._running = False
        self.available = _PICAMERA2_AVAILABLE

    def start(self) -> None:
        if not _PICAMERA2_AVAILABLE:
            logger.warning("Picamera2 not available — camera stream disabled")
            self.available = False
            return

        assert Picamera2_cls is not None
        assert MJPEGEncoder_cls is not None
        assert FileOutput_cls is not None

        try:
            self._picam2 = Picamera2_cls()
            video_config = self._picam2.create_video_configuration(
                main={"size": (self._config.width, self._config.height)},
                controls={"FrameRate": self._config.fps},
            )
            self._picam2.configure(video_config)
            encoder = MJPEGEncoder_cls(bitrate=None)
            file_output = FileOutput_cls(self._output)
            quality = parse_mjpeg_quality(self._config.quality)
            self._picam2.start_recording(encoder, file_output, quality=quality)
            self._running = True
            self.available = True
            logger.info(
                "Camera started %dx%d @ %d fps quality=%s",
                self._config.width,
                self._config.height,
                self._config.fps,
                self._config.quality,
            )
        except Exception:
            logger.exception("Failed to start camera")
            self.available = False
            self._running = False
            self._cleanup_picam()

    def stop(self) -> None:
        self._running = False
        self._cleanup_picam()
        with self._output._condition:
            self._output._condition.notify_all()
        logger.info("Camera stopped")

    def _cleanup_picam(self) -> None:
        if self._picam2 is None:
            return
        try:
            if self._running:
                self._picam2.stop_recording()
        except Exception:
            logger.debug("stop_recording failed", exc_info=True)
        try:
            self._picam2.close()
        except Exception:
            logger.debug("picam close failed", exc_info=True)
        self._picam2 = None

    def iter_frames(self) -> Iterator[bytes]:
        """Yield new JPEG frames; blocks until encoder delivers a new buffer."""
        last: bytes | None = None
        while self._running:
            frame = self._output.wait_for_new_frame(last, timeout=1.0)
            if frame is None:
                continue
            last = frame
            yield frame

    async def async_frame_parts(self) -> AsyncIterator[bytes]:
        """Async multipart chunks for StreamingResponse."""
        loop = asyncio.get_running_loop()
        last: bytes | None = None
        while self._running:
            frame = await loop.run_in_executor(
                None, self._output.wait_for_new_frame, last, 1.0
            )
            if frame is None:
                continue
            last = frame
            yield format_mjpeg_part(frame)
