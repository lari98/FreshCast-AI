"""Remembers trained forecasts per group of stores (unchanged stores are not retrained).

The key is a hash of everything that decides the result (the group rows, the
as-of date, the calibration setting and ``MODEL_VERSION``). Results live in memory only,
for a limited time, and a hit needs byte-identical data, so one user can never receive
another user's forecast without having uploaded the same numbers.
"""

from __future__ import annotations

import hashlib
import threading
import time
from collections import OrderedDict

import pandas as pd

# Raise when the model, features or calibration change, so old entries are never reused.
MODEL_VERSION = "2026-11-quantile-cqr-1"


def frame_key(frame: pd.DataFrame, *extra: object) -> str:
    """Content hash of a feature frame plus the settings that shape the forecast."""
    h = hashlib.sha256(MODEL_VERSION.encode())
    h.update(
        repr((list(frame.columns), [str(t) for t in frame.dtypes], extra)).encode()
    )
    h.update(pd.util.hash_pandas_object(frame, index=False).to_numpy().tobytes())
    return h.hexdigest()


class ForecastCache:
    """Thread-safe LRU with a time limit holding forecast frames."""

    def __init__(self, entries: int = 64, ttl_seconds: int = 3600) -> None:
        """Keep at most ``entries`` frames, each for ``ttl_seconds``."""
        self._entries = max(0, entries)
        self._ttl = ttl_seconds
        self._data: OrderedDict[str, tuple[float, pd.DataFrame]] = OrderedDict()
        self._lock = threading.Lock()
        self.hits = 0
        self.misses = 0

    def get(self, key: str, now: float | None = None) -> pd.DataFrame | None:
        """Return a copy of a fresh entry, or ``None``."""
        now = time.monotonic() if now is None else now
        with self._lock:
            hit = self._data.get(key)
            if hit is None or now - hit[0] > self._ttl:
                self._data.pop(key, None)
                self.misses += 1
                return None
            self._data.move_to_end(key)
            self.hits += 1
            return hit[1].copy()

    def put(self, key: str, frame: pd.DataFrame, now: float | None = None) -> None:
        """Store a copy; the least recently used entry is dropped when full."""
        if self._entries == 0:
            return
        now = time.monotonic() if now is None else now
        with self._lock:
            self._data[key] = (now, frame.copy())
            self._data.move_to_end(key)
            while len(self._data) > self._entries:
                self._data.popitem(last=False)

    def clear(self) -> None:
        """Forget everything (tests, or a model change)."""
        with self._lock:
            self._data.clear()
            self.hits = self.misses = 0


FORECASTS = ForecastCache()
