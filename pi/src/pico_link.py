"""UART link to Raspberry Pi Pico with command batching and telemetry."""

from __future__ import annotations

import asyncio
import logging
import re
import threading
import time
from typing import Any

import serial
from serial import SerialException

from src.config import SerialConfig

logger = logging.getLogger(__name__)

_STAT_RE = re.compile(
    r"^STAT\s+batt=(?P<batt>[\d.]+)\s+dist=(?P<dist>\d+)\s+up=(?P<up>[01])\s*$"
)

_SEND_INTERVAL_S = 0.05


class PicoLink:
    """Async-friendly UART bridge to Pico with 50 ms command coalescing."""

    def __init__(self, serial_cfg: SerialConfig) -> None:
        self._serial_cfg = serial_cfg
        self._port: serial.Serial | None = None
        self._connected = False
        self._telemetry: dict[str, Any] = {}
        self._telemetry_lock = threading.Lock()
        self._read_thread: threading.Thread | None = None
        self._read_stop = threading.Event()
        self._queue: asyncio.Queue[str | None] | None = None
        self._sender_task: asyncio.Task[None] | None = None
        self._reconnect_task: asyncio.Task[None] | None = None
        self._loop: asyncio.AbstractEventLoop | None = None
        self._closing = False

    @property
    def connected(self) -> bool:
        return self._connected

    @property
    def telemetry(self) -> dict[str, Any]:
        with self._telemetry_lock:
            return dict(self._telemetry)

    def start(self) -> None:
        """Start background tasks (call from running event loop)."""
        self._loop = asyncio.get_running_loop()
        self._queue = asyncio.Queue()
        self._sender_task = asyncio.create_task(self._sender_loop())
        self._reconnect_task = asyncio.create_task(self._reconnect_loop())
        self._try_open_port()

    async def close(self) -> None:
        """Stop tasks, send STOP, close serial port."""
        self._closing = True
        self._read_stop.set()

        if self._connected:
            await asyncio.to_thread(self._write_line, "STOP\n")

        if self._queue is not None:
            await self._queue.put(None)

        for task in (self._sender_task, self._reconnect_task):
            if task is not None:
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass

        if self._read_thread is not None and self._read_thread.is_alive():
            self._read_thread.join(timeout=1.0)

        self._close_port()

    async def send_drive(self, left: int, right: int) -> None:
        await self._enqueue(f"DRIVE {left} {right}\n")

    async def send_cam(self, pan: int, tilt: int) -> None:
        await self._enqueue(f"CAM {pan} {tilt}\n")

    async def send_stop(self) -> None:
        await self._enqueue("STOP\n")

    async def send_ping(self) -> None:
        await self._enqueue("PING\n")

    async def _enqueue(self, line: str) -> None:
        if self._queue is None or self._closing:
            return
        await self._queue.put(line)

    def _try_open_port(self) -> None:
        if self._closing or self._connected:
            return
        if self._read_thread is not None and self._read_thread.is_alive():
            self._read_stop.set()
            self._read_thread.join(timeout=0.5)
            self._read_stop.clear()
        try:
            port = serial.Serial(
                self._serial_cfg.port,
                self._serial_cfg.baud,
                timeout=0.1,
            )
        except (SerialException, OSError) as exc:
            logger.warning("Cannot open serial port %s: %s", self._serial_cfg.port, exc)
            self._connected = False
            return

        self._port = port
        self._connected = True
        logger.info("Serial port %s opened", self._serial_cfg.port)

        self._read_stop.clear()
        self._read_thread = threading.Thread(
            target=self._read_loop,
            name="pico-serial-read",
            daemon=True,
        )
        self._read_thread.start()

    def _close_port(self) -> None:
        self._connected = False
        if self._port is not None:
            try:
                self._port.close()
            except OSError as exc:
                logger.debug("Error closing serial port: %s", exc)
            self._port = None

    def _write_line(self, line: str) -> None:
        if not self._connected or self._port is None:
            return
        try:
            self._port.write(line.encode("ascii"))
            self._port.flush()
            logger.debug("UART -> %s", line.strip())
        except (SerialException, OSError) as exc:
            logger.warning("Serial write failed: %s", exc)
            self._handle_disconnect()

    def _handle_disconnect(self) -> None:
        self._read_stop.set()
        self._close_port()

    def _read_loop(self) -> None:
        while not self._read_stop.is_set():
            port = self._port
            if port is None or not self._connected:
                time.sleep(0.05)
                continue
            try:
                raw = port.readline()
            except (SerialException, OSError) as exc:
                logger.warning("Serial read failed: %s", exc)
                self._handle_disconnect()
                break
            if not raw:
                continue
            try:
                line = raw.decode("ascii", errors="ignore").strip()
            except UnicodeDecodeError:
                continue
            if not line:
                continue
            self._parse_line(line)

    def _parse_line(self, line: str) -> None:
        match = _STAT_RE.match(line)
        if not match:
            logger.debug("UART <- (ignored) %s", line)
            return
        parsed = {
            "batt_v": float(match.group("batt")),
            "dist_cm": int(match.group("dist")),
            "up": int(match.group("up")),
        }
        with self._telemetry_lock:
            self._telemetry = parsed
        logger.debug("UART <- STAT %s", parsed)

    async def _sender_loop(self) -> None:
        assert self._queue is not None
        loop = asyncio.get_running_loop()
        while True:
            line = await self._queue.get()
            if line is None:
                break

            pending = line
            deadline = loop.time() + _SEND_INTERVAL_S
            while True:
                remaining = deadline - loop.time()
                if remaining <= 0:
                    break
                try:
                    nxt = await asyncio.wait_for(self._queue.get(), timeout=remaining)
                except asyncio.TimeoutError:
                    break
                if nxt is None:
                    await asyncio.to_thread(self._write_line, pending)
                    return
                pending = nxt

            await asyncio.to_thread(self._write_line, pending)

    async def _reconnect_loop(self) -> None:
        while not self._closing:
            await asyncio.sleep(self._serial_cfg.reconnect_seconds)
            if self._closing or self._connected:
                continue
            logger.debug("Attempting serial reconnect to %s", self._serial_cfg.port)
            await asyncio.to_thread(self._try_open_port)
