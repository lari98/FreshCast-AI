"""Keeps the heavy upload analysis cheap and bounded: a result cache and a load gate."""

from __future__ import annotations

import hashlib
import threading
import time
from collections import OrderedDict
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any


def cache_key(sales: bytes, stock: bytes | None, as_of: object) -> str:
    """Content hash of everything that decides the result."""
    h = hashlib.sha256()
    for part in (sales, stock or b"", str(as_of).encode()):
        h.update(len(part).to_bytes(8, "big"))
        h.update(part)
    return h.hexdigest()


class ResultCache:
    """Small thread-safe LRU with a time limit; results are never written to disk."""

    def __init__(self, entries: int, ttl_seconds: int) -> None:
        """Hold at most ``entries`` results, each for ``ttl_seconds``."""
        self._entries = max(0, entries)
        self._ttl = ttl_seconds
        self._data: OrderedDict[str, tuple[float, dict[str, Any]]] = OrderedDict()
        self._lock = threading.Lock()

    def get(self, key: str, now: float | None = None) -> dict[str, Any] | None:
        """Return a fresh cached result and mark it recently used."""
        now = time.monotonic() if now is None else now
        with self._lock:
            hit = self._data.get(key)
            if hit is None:
                return None
            if now - hit[0] > self._ttl:
                del self._data[key]
                return None
            self._data.move_to_end(key)
            return hit[1]

    def put(self, key: str, value: dict[str, Any], now: float | None = None) -> None:
        """Store a result, evicting the least recently used one when full."""
        if self._entries == 0:
            return
        now = time.monotonic() if now is None else now
        with self._lock:
            self._data[key] = (now, value)
            self._data.move_to_end(key)
            while len(self._data) > self._entries:
                self._data.popitem(last=False)


class Busy(Exception):
    """Raised when the analysis capacity is used up."""


class LoadGate:
    """Allows a fixed number of analyses at once; never queues (no hidden pile-up)."""

    def __init__(self, limit: int) -> None:
        """Allow ``limit`` simultaneous analyses (at least one)."""
        self._sem = threading.BoundedSemaphore(max(1, limit))

    @contextmanager
    def slot(self) -> Iterator[None]:
        """Hold a slot for the duration of the block, or raise :class:`Busy`."""
        if not self._sem.acquire(blocking=False):
            raise Busy
        try:
            yield
        finally:
            self._sem.release()
