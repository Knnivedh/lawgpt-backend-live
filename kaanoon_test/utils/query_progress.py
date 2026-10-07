"""Lightweight per-thread progress bus for live query streaming.

The stream endpoint registers a callback for the request's thread; pipeline
stages call emit() which is a no-op when no callback is registered (the
normal /api/query path pays zero cost).
"""
import threading
import time

_local = threading.local()


def set_callback(cb):
    _local.cb = cb


def clear_callback():
    _local.cb = None


def has_callback() -> bool:
    return getattr(_local, "cb", None) is not None


def emit(stage: str, message: str = "", data=None):
    cb = getattr(_local, "cb", None)
    if cb is None:
        return
    try:
        cb({
            "type": stage,
            "message": message,
            "data": data or {},
            "ts": round(time.time(), 3),
        })
    except Exception:
        pass
