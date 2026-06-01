"""FastAPI application: MJPEG stream, WebSocket control, status API."""

from __future__ import annotations

import asyncio
import logging
import time
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, AsyncIterator

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse

from src.camera import CameraStream
from src.config import AppConfig, clamp
from src.pico_link import PicoLink

logger = logging.getLogger(__name__)

_WEB_DIR = Path(__file__).resolve().parent / "web"
_WATCHDOG_INTERVAL_S = 0.05


@dataclass
class AppState:
    config: AppConfig
    camera: CameraStream
    pico: PicoLink
    started_at: float = field(default_factory=time.monotonic)
    mode: str = "idle"
    control_active: bool = False
    last_control_monotonic: float = 0.0


def create_app(config: AppConfig) -> FastAPI:
    camera = CameraStream(config.camera)
    pico = PicoLink(config.serial, config.safety)
    state = AppState(config=config, camera=camera, pico=pico)
    watchdog_task: asyncio.Task[None] | None = None

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        nonlocal watchdog_task
        camera.start()
        await pico.start()
        watchdog_task = asyncio.create_task(_control_watchdog(state))
        logger.info("Application started")
        yield
        if watchdog_task is not None:
            watchdog_task.cancel()
            try:
                await watchdog_task
            except asyncio.CancelledError:
                pass
        pico.send_stop()
        await pico.stop()
        camera.stop()
        logger.info("Application stopped")

    app = FastAPI(title="RP3 Tank Control", lifespan=lifespan)
    app.state.rp3 = state

    @app.get("/")
    async def index() -> FileResponse:
        return FileResponse(_WEB_DIR / "index.html")

    @app.get("/status")
    async def status() -> dict[str, Any]:
        telem = pico.telemetry
        return {
            "uptime_s": round(time.monotonic() - state.started_at, 1),
            "pico_connected": pico.connected,
            "batt_v": telem.batt_v if telem is not None else None,
            "dist_cm": telem.dist_cm if telem is not None else None,
            "mode": state.mode,
        }

    @app.get("/stream.mjpg", response_model=None)
    async def stream_mjpg() -> StreamingResponse | JSONResponse:
        if not camera.available:
            return JSONResponse(
                status_code=503,
                content={"detail": "Camera not available"},
            )

        async def generate() -> AsyncIterator[bytes]:
            async for part in camera.async_frame_parts():
                yield part

        return StreamingResponse(
            generate(),
            media_type="multipart/x-mixed-replace; boundary=frame",
        )

    @app.websocket("/ws/control")
    async def ws_control(websocket: WebSocket) -> None:
        await websocket.accept()
        logger.debug("WebSocket client connected")
        try:
            while True:
                raw = await websocket.receive_json()
                _handle_control_message(state, raw)
        except WebSocketDisconnect:
            logger.debug("WebSocket client disconnected")
        except Exception as exc:
            logger.debug("WebSocket error: %s", exc)
        finally:
            if state.control_active:
                pico.send_stop()
                state.control_active = False
                state.mode = "idle"

    return app


async def _control_watchdog(state: AppState) -> None:
    timeout_s = state.config.safety.control_timeout_ms / 1000.0
    while True:
        await asyncio.sleep(_WATCHDOG_INTERVAL_S)
        if not state.control_active:
            continue
        elapsed = time.monotonic() - state.last_control_monotonic
        if elapsed > timeout_s:
            logger.warning(
                "Control timeout (%.0f ms) — failsafe STOP",
                state.config.safety.control_timeout_ms,
            )
            state.pico.send_stop()
            state.mode = "failsafe"
            state.control_active = False


def _handle_control_message(state: AppState, raw: Any) -> None:
    if not isinstance(raw, dict):
        logger.debug("Ignoring non-object WS message: %r", raw)
        return

    msg_type = raw.get("type")
    now = time.monotonic()
    safety = state.config.safety

    if msg_type == "drive":
        left = clamp(int(raw.get("left", 0)), -100, 100)
        right = clamp(int(raw.get("right", 0)), -100, 100)
        state.pico.set_drive(left, right)
        state.mode = "drive"
        state.control_active = True
        state.last_control_monotonic = now
    elif msg_type == "cam":
        pan = clamp(int(raw.get("pan", 90)), safety.pan_min, safety.pan_max)
        tilt = clamp(int(raw.get("tilt", 90)), safety.tilt_min, safety.tilt_max)
        state.pico.set_cam(pan, tilt)
        state.mode = "cam"
        state.control_active = True
        state.last_control_monotonic = now
    elif msg_type == "stop":
        state.pico.send_stop()
        state.mode = "idle"
        state.control_active = False
        state.last_control_monotonic = now
    else:
        logger.debug("Unknown WS message type: %r", msg_type)
