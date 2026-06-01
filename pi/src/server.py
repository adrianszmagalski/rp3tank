"""FastAPI application: MJPEG stream, WebSocket control, status API."""

from __future__ import annotations

import asyncio
import logging
import time
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, AsyncIterator

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, JSONResponse, Response, StreamingResponse

from src.camera import CameraStream
from src.config import AppConfig, clamp
from src.pico_link import PicoLink

logger = logging.getLogger(__name__)

_WEB_DIR = Path(__file__).resolve().parent / "web"
_BOUNDARY = b"--frame"
_WATCHDOG_POLL_S = 0.1


def create_app(config: AppConfig, camera: CameraStream, pico: PicoLink) -> FastAPI:
    safety = config.safety
    assert safety is not None

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        app.state.start_time = time.monotonic()
        app.state.mode = "idle"
        app.state.last_control = 0.0
        app.state.watchdog_tripped = False
        app.state.control_active = False

        pico.start()
        watchdog_task = asyncio.create_task(_watchdog_loop(app, pico, safety.control_timeout_ms))

        logger.info("Control server started")
        try:
            yield
        finally:
            watchdog_task.cancel()
            try:
                await watchdog_task
            except asyncio.CancelledError:
                pass
            await pico.close()
            camera.stop()
            logger.info("Control server stopped")

    app = FastAPI(title="RP3 Tank Control", lifespan=lifespan)

    @app.get("/")
    async def index() -> FileResponse:
        return FileResponse(_WEB_DIR / "index.html")

    @app.get("/status")
    async def status() -> JSONResponse:
        telem = pico.telemetry
        uptime = time.monotonic() - app.state.start_time
        return JSONResponse(
            {
                "uptime_s": round(uptime, 1),
                "pico_connected": pico.connected,
                "batt_v": telem.get("batt_v"),
                "dist_cm": telem.get("dist_cm"),
                "mode": app.state.mode,
            }
        )

    @app.get("/stream.mjpg")
    async def stream_mjpg() -> Response:
        if not camera.available:
            return JSONResponse(
                status_code=503,
                content={"detail": "Camera not available"},
            )

        return StreamingResponse(
            _mjpeg_generator(camera),
            media_type="multipart/x-mixed-replace; boundary=frame",
        )

    @app.websocket("/ws/control")
    async def ws_control(websocket: WebSocket) -> None:
        await websocket.accept()
        logger.info("WebSocket client connected")
        try:
            while True:
                data: dict[str, Any] = await websocket.receive_json()
                await _handle_control_message(app, pico, safety, data)
        except WebSocketDisconnect:
            logger.info("WebSocket client disconnected")
        except Exception as exc:
            logger.warning("WebSocket error: %s", exc)

    return app


async def _mjpeg_generator(camera: CameraStream) -> AsyncIterator[bytes]:
    while camera.available:
        frame = await asyncio.to_thread(camera.wait_frame, 1.0)
        if frame is None:
            continue
        yield (
            _BOUNDARY
            + b"\r\nContent-Type: image/jpeg\r\n\r\n"
            + frame
            + b"\r\n"
        )


async def _handle_control_message(
    app: FastAPI,
    pico: PicoLink,
    safety: Any,
    data: dict[str, Any],
) -> None:
    msg_type = data.get("type")
    if not isinstance(msg_type, str):
        logger.debug("Ignoring message without type: %s", data)
        return

    if msg_type == "drive":
        left = _as_int(data.get("left"), 0)
        right = _as_int(data.get("right"), 0)
        left = clamp(left, -100, 100)
        right = clamp(right, -100, 100)
        await pico.send_drive(left, right)
        _mark_control(app)
        logger.debug("drive left=%d right=%d", left, right)

    elif msg_type == "cam":
        pan = _as_int(data.get("pan"), safety.pan_min)
        tilt = _as_int(data.get("tilt"), safety.tilt_min)
        pan = clamp(pan, safety.pan_min, safety.pan_max)
        tilt = clamp(tilt, safety.tilt_min, safety.tilt_max)
        await pico.send_cam(pan, tilt)
        _mark_control(app)
        logger.debug("cam pan=%d tilt=%d", pan, tilt)

    elif msg_type == "stop":
        await pico.send_stop()
        app.state.control_active = False
        app.state.mode = "idle"
        logger.debug("stop")

    else:
        logger.debug("Unknown control type: %s", msg_type)


def _mark_control(app: FastAPI) -> None:
    app.state.last_control = time.monotonic()
    app.state.control_active = True
    app.state.watchdog_tripped = False
    app.state.mode = "active"


def _as_int(value: Any, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


async def _watchdog_loop(
    app: FastAPI,
    pico: PicoLink,
    control_timeout_ms: int,
) -> None:
    timeout_s = control_timeout_ms / 1000.0
    while True:
        await asyncio.sleep(_WATCHDOG_POLL_S)
        if not app.state.control_active:
            continue
        if app.state.watchdog_tripped:
            continue
        elapsed = time.monotonic() - app.state.last_control
        if elapsed > timeout_s:
            logger.warning(
                "Control watchdog triggered after %.0f ms, sending STOP",
                elapsed * 1000,
            )
            await pico.send_stop()
            app.state.watchdog_tripped = True
            app.state.control_active = False
            app.state.mode = "failsafe"
