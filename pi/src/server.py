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
from src.event_log import EventLog
from src.pico_link import PicoLink

logger = logging.getLogger(__name__)

_WEB_DIR = Path(__file__).resolve().parent / "web"
_WATCHDOG_INTERVAL_S = 0.05
_DIAGNOSTICS_INTERVAL_S = 0.25


@dataclass
class DiagnosticsSnapshot:
    pico_alive: bool = False
    pico_connected: bool = False
    mode: str = "idle"
    batt_low_latched: bool = False


@dataclass
class AppState:
    config: AppConfig
    camera: CameraStream
    pico: PicoLink
    event_log: EventLog
    started_at: float = field(default_factory=time.monotonic)
    mode: str = "idle"
    control_active: bool = False
    last_control_monotonic: float = 0.0
    diag_snapshot: DiagnosticsSnapshot = field(default_factory=DiagnosticsSnapshot)


def create_app(config: AppConfig) -> FastAPI:
    started_at = time.monotonic()
    event_log = EventLog(
        maxlen=config.diagnostics.events_buffer_size,
        started_at_monotonic=started_at,
    )
    camera = CameraStream(config.camera)
    pico = PicoLink(config.serial, config.safety, config.diagnostics, event_log)
    state = AppState(
        config=config,
        camera=camera,
        pico=pico,
        event_log=event_log,
        started_at=started_at,
    )
    watchdog_task: asyncio.Task[None] | None = None
    diagnostics_task: asyncio.Task[None] | None = None

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        nonlocal watchdog_task, diagnostics_task
        camera.start()
        await pico.start()
        watchdog_task = asyncio.create_task(_control_watchdog(state))
        diagnostics_task = asyncio.create_task(_diagnostics_loop(state))
        logger.info("Application started")
        yield
        if diagnostics_task is not None:
            diagnostics_task.cancel()
            try:
                await diagnostics_task
            except asyncio.CancelledError:
                pass
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
            "pico_alive": pico.alive,
            "stat_age_ms": pico.stat_age_ms,
            "batt_v": telem.batt_v if telem is not None else None,
            "dist_cm": telem.dist_cm if telem is not None else None,
            "mode": state.mode,
        }

    @app.get("/events")
    async def events() -> dict[str, Any]:
        """Ring of recent events, oldest first, newest at end."""
        return {"events": event_log.snapshot()}

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
        event_log.emit("info", "ws_connect", "Klient WebSocket połączony")
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
            event_log.emit("warning", "ws_disconnect", "Klient WebSocket rozłączony")
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


async def _diagnostics_loop(state: AppState) -> None:
    diag = state.config.diagnostics
    snap = state.diag_snapshot
    log = state.event_log
    batt_ok_threshold = diag.batt_warn_v + diag.batt_warn_hysteresis_v

    while True:
        await asyncio.sleep(_DIAGNOSTICS_INTERVAL_S)

        pico_alive = state.pico.alive
        pico_connected = state.pico.connected
        mode = state.mode
        telem = state.pico.telemetry
        batt_v = telem.batt_v if telem is not None else None

        if pico_alive and not snap.pico_alive:
            log.emit("info", "pico_alive", "Pico żywy — świeże ramki STAT")
        elif not pico_alive and snap.pico_alive:
            log.emit("critical", "pico_dead", "Pico martwe — brak świeżych ramek STAT")

        if mode == "failsafe" and snap.mode != "failsafe":
            log.emit("critical", "failsafe_enter", "Wejście w tryb failsafe (timeout sterowania)")
        elif mode != "failsafe" and snap.mode == "failsafe":
            log.emit("info", "failsafe_exit", "Wyjście z trybu failsafe")

        if pico_connected and not snap.pico_connected:
            log.emit("info", "uart_connect", "Port UART otwarty")
        elif not pico_connected and snap.pico_connected:
            log.emit("warning", "uart_disconnect", "Port UART zamknięty")

        batt_valid = batt_v is not None and batt_v > diag.batt_min_valid_v
        if batt_valid:
            if batt_v < diag.batt_warn_v and not snap.batt_low_latched:
                log.emit(
                    "warning",
                    "batt_low",
                    f"Niskie napięcie baterii AA: {batt_v:.2f} V",
                )
                snap.batt_low_latched = True
            elif batt_v > batt_ok_threshold and snap.batt_low_latched:
                log.emit(
                    "info",
                    "batt_ok",
                    f"Napięcie baterii AA wróciło do normy: {batt_v:.2f} V",
                )
                snap.batt_low_latched = False

        snap.pico_alive = pico_alive
        snap.pico_connected = pico_connected
        snap.mode = mode


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
