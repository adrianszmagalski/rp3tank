"""UART link to Raspberry Pi Pico with command coalescing and telemetry."""

from __future__ import annotations

import asyncio
import logging
import re
import threading
import time
from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal

import serial
from serial import SerialException

from src.config import DiagnosticsConfig, SafetyConfig, SerialConfig, clamp

if TYPE_CHECKING:
    from src.event_log import EventLog

logger = logging.getLogger(__name__)

_STAT_RE = re.compile(
    r"^STAT\s+batt=(?P<batt>[\d.]+)\s+dist=(?P<dist>\d+)\s+up=(?P<up>[01])\s*$"
)

_COALESCE_INTERVAL_S = 0.05
_THREAD_JOIN_TIMEOUT_S = 1.0


@dataclass
class Telemetry:
    batt_v: float
    dist_cm: int
    up: bool


@dataclass
class _PendingCommand:
    kind: Literal["drive", "cam", "stop", "ping"]
    left: int = 0
    right: int = 0
    pan: int = 90
    tilt: int = 90


class PicoLink:
    """Async-friendly UART bridge to Pico with 50 ms command coalescing."""

    def __init__(
        self,
        serial_cfg: SerialConfig,
        safety_cfg: SafetyConfig,
        diagnostics_cfg: DiagnosticsConfig,
        event_log: EventLog | None = None,
    ) -> None:
        self._serial_cfg = serial_cfg
        self._safety = safety_cfg
        self._diagnostics = diagnostics_cfg
        self._event_log = event_log
        self._ser: serial.Serial | None = None
        self._connected = False
        self._telemetry: Telemetry | None = None
        self._last_stat_monotonic: float | None = None
        self._telemetry_lock = threading.Lock()
        self._cmd_lock = threading.Lock()
        self._port_lock = threading.Lock()
        self._disconnect_lock = threading.Lock()
        self._pending: _PendingCommand | None = None
        self._stop_event = threading.Event()
        self._reader_thread: threading.Thread | None = None
        self._sender_thread: threading.Thread | None = None
        self._reconnect_task: asyncio.Task[None] | None = None
        self._running = False

    @property
    def connected(self) -> bool:
        return self._connected

    @property
    def stat_age_ms(self) -> int | None:
        with self._telemetry_lock:
            if self._last_stat_monotonic is None:
                return None
            age_ms = int((time.monotonic() - self._last_stat_monotonic) * 1000)
            return age_ms

    @property
    def alive(self) -> bool:
        age = self.stat_age_ms
        if age is None:
            return False
        return age < self._diagnostics.pico_stale_ms

    @property
    def telemetry(self) -> Telemetry | None:
        with self._telemetry_lock:
            return self._telemetry

    def _reset_stat_timestamp(self) -> None:
        with self._telemetry_lock:
            self._last_stat_monotonic = None

    async def start(self) -> None:
        if self._running:
            return
        self._running = True
        self._stop_event.clear()
        self._reconnect_task = asyncio.create_task(self._reconnect_loop())
        logger.info("PicoLink started (port=%s)", self._serial_cfg.port)

    async def stop(self) -> None:
        self._running = False
        if self._reconnect_task is not None:
            self._reconnect_task.cancel()
            try:
                await self._reconnect_task
            except asyncio.CancelledError:
                pass
            self._reconnect_task = None
        await asyncio.to_thread(self._disconnect)
        logger.info("PicoLink stopped")

    def set_drive(self, left: int, right: int) -> None:
        left = clamp(left, -100, 100)
        right = clamp(right, -100, 100)
        with self._cmd_lock:
            self._pending = _PendingCommand("drive", left=left, right=right)

    def set_cam(self, pan: int, tilt: int) -> None:
        pan = clamp(pan, self._safety.pan_min, self._safety.pan_max)
        tilt = clamp(tilt, self._safety.tilt_min, self._safety.tilt_max)
        with self._cmd_lock:
            self._pending = _PendingCommand("cam", pan=pan, tilt=tilt)

    def send_stop(self) -> None:
        with self._cmd_lock:
            self._pending = _PendingCommand("stop")

    def ping(self) -> None:
        with self._cmd_lock:
            self._pending = _PendingCommand("ping")

    async def _reconnect_loop(self) -> None:
        while self._running:
            if not self._connected:
                await asyncio.to_thread(self._try_connect)
            await asyncio.sleep(self._serial_cfg.reconnect_seconds)

    def _try_connect(self) -> None:
        if self._connected:
            return
        self._reset_stat_timestamp()
        try:
            ser = serial.Serial(
                self._serial_cfg.port,
                self._serial_cfg.baud,
                timeout=0.1,
            )
        except (SerialException, OSError) as exc:
            logger.debug("UART connect failed: %s", exc)
            self._connected = False
            return

        with self._port_lock:
            self._ser = ser
        self._connected = True
        self._stop_event.clear()
        self._reader_thread = threading.Thread(
            target=self._reader_loop, name="pico-uart-reader", daemon=True
        )
        self._sender_thread = threading.Thread(
            target=self._sender_loop, name="pico-uart-sender", daemon=True
        )
        self._reader_thread.start()
        self._sender_thread.start()
        logger.info("UART connected on %s", self._serial_cfg.port)

    def _take_serial(self) -> serial.Serial | None:
        with self._port_lock:
            ser = self._ser
            self._ser = None
            return ser

    def _close_serial(self, ser: serial.Serial | None) -> None:
        if ser is None:
            return
        try:
            ser.close()
        except (SerialException, OSError, TypeError):
            pass

    def _send_stop_on_serial(self, ser: serial.Serial) -> None:
        try:
            ser.write(b"STOP\n")
            ser.flush()
        except (SerialException, OSError, TypeError):
            pass

    def _disconnect(self) -> None:
        with self._disconnect_lock:
            self._stop_event.set()
            self._connected = False
            self._reset_stat_timestamp()

            with self._port_lock:
                ser_for_stop = self._ser
            if ser_for_stop is not None:
                self._send_stop_on_serial(ser_for_stop)

            reader = self._reader_thread
            sender = self._sender_thread
            current = threading.current_thread()
            if reader is not None and reader is not current:
                reader.join(timeout=_THREAD_JOIN_TIMEOUT_S)
            if sender is not None and sender is not current:
                sender.join(timeout=_THREAD_JOIN_TIMEOUT_S)

            ser = self._take_serial()
            self._close_serial(ser)
            self._reader_thread = None
            self._sender_thread = None

    def _reader_loop(self) -> None:
        with self._port_lock:
            if self._ser is None:
                return
        buf = ""
        while not self._stop_event.is_set() and self._connected:
            try:
                with self._port_lock:
                    ser = self._ser
                if ser is None:
                    return
                chunk = ser.read(256)
            except (SerialException, OSError, TypeError) as exc:
                if self._stop_event.is_set():
                    logger.debug("UART read during shutdown: %s", exc)
                    return
                logger.warning("UART read error: %s", exc)
                self._handle_disconnect()
                return
            if not chunk:
                continue
            buf += chunk.decode("ascii", errors="ignore")
            while "\n" in buf:
                line, buf = buf.split("\n", 1)
                line = line.strip()
                if line:
                    self._handle_line(line)

    def _handle_line(self, line: str) -> None:
        match = _STAT_RE.match(line)
        if not match:
            logger.debug("UART RX: %s", line)
            if self._event_log is not None:
                snippet = line if len(line) <= 48 else line[:45] + "..."
                self._event_log.emit(
                    "warning",
                    "uart_parse_error",
                    f"Błąd parsowania UART: {snippet}",
                    debounce=True,
                )
            return
        telem = Telemetry(
            batt_v=float(match.group("batt")),
            dist_cm=int(match.group("dist")),
            up=match.group("up") == "1",
        )
        with self._telemetry_lock:
            self._telemetry = telem
            self._last_stat_monotonic = time.monotonic()
        logger.debug("Telemetry: batt=%.2f dist=%d", telem.batt_v, telem.dist_cm)

    def _handle_disconnect(self) -> None:
        self._connected = False
        self._reset_stat_timestamp()
        ser = self._take_serial()
        self._close_serial(ser)

    def _sender_loop(self) -> None:
        while not self._stop_event.is_set() and self._connected:
            with self._cmd_lock:
                cmd = self._pending
                self._pending = None
            if cmd is not None:
                line = self._format_command(cmd)
                self._write_line(line)
            self._stop_event.wait(_COALESCE_INTERVAL_S)

    def _format_command(self, cmd: _PendingCommand) -> str:
        if cmd.kind == "drive":
            return f"DRIVE {cmd.left} {cmd.right}"
        if cmd.kind == "cam":
            return f"CAM {cmd.pan} {cmd.tilt}"
        if cmd.kind == "stop":
            return "STOP"
        return "PING"

    def _write_line(self, line: str) -> None:
        if self._ser is None or not self._connected:
            return
        try:
            self._ser.write(f"{line}\n".encode("ascii"))
            self._ser.flush()
            logger.debug("UART TX: %s", line)
        except (SerialException, OSError, TypeError) as exc:
            if self._stop_event.is_set():
                logger.debug("UART write during shutdown: %s", exc)
                return
            logger.warning("UART write error: %s", exc)
            self._handle_disconnect()
