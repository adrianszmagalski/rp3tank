"""In-memory ring buffer of diagnostic events (newest at end)."""

from __future__ import annotations

import logging
import threading
import time
from collections import deque
from dataclasses import dataclass
from typing import Any, Literal

logger = logging.getLogger(__name__)

EventLevel = Literal["info", "warning", "critical"]

_LEVEL_TO_LOGGING = {
    "info": logging.INFO,
    "warning": logging.WARNING,
    "critical": logging.ERROR,
}


@dataclass(frozen=True)
class Event:
    ts: float
    level: EventLevel
    code: str
    message: str


class EventLog:
    """Thread-safe ring buffer; events ordered oldest → newest (append at end)."""

    def __init__(
        self,
        maxlen: int,
        started_at_monotonic: float,
        debounce_s: float = 5.0,
    ) -> None:
        self._deque: deque[Event] = deque(maxlen=maxlen)
        self._lock = threading.Lock()
        self._started_at = started_at_monotonic
        self._debounce_s = debounce_s
        self._last_emit_monotonic: dict[str, float] = {}

    def emit(
        self,
        level: EventLevel,
        code: str,
        message: str,
        *,
        debounce: bool = False,
    ) -> None:
        now = time.monotonic()
        if debounce:
            with self._lock:
                last = self._last_emit_monotonic.get(code)
                if last is not None and (now - last) < self._debounce_s:
                    return
                self._last_emit_monotonic[code] = now

        ts = round(now - self._started_at, 1)
        event = Event(ts=ts, level=level, code=code, message=message)
        with self._lock:
            self._deque.append(event)

        log_level = _LEVEL_TO_LOGGING[level]
        logger.log(log_level, "[%s] %s", code, message)

    def snapshot(self) -> list[dict[str, Any]]:
        with self._lock:
            return [
                {
                    "ts": e.ts,
                    "level": e.level,
                    "code": e.code,
                    "message": e.message,
                }
                for e in self._deque
            ]
