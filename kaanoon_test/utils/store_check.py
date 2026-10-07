"""Startup reachability check for the configured vector store.

The corpus went dark without anyone noticing: the Zilliz serverless cluster had
been suspended by the provider (free-tier auto-suspend), so every query fell
through to web fallback + model memory while the UI still advertised a large
document count. This check makes that condition loud at boot and in /api/health.

It never raises and never blocks startup - a retrieval outage must degrade, not
crash, the API.
"""
from __future__ import annotations

import logging
import threading
import time
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

_STATE: Dict[str, Any] = {
    "mode": "unknown",          # cloud | local | disabled
    "reachable": None,          # None = not probed yet
    "detail": "not probed yet",
    "last_probe_ts": None,
    "documents": None,
    "latency_s": None,
    "collection": None,
    "endpoint_host": None,
}
_LOCK = threading.Lock()


def _probe_cloud() -> Dict[str, Any]:
    import os

    endpoint = (os.getenv("ZILLIZ_CLUSTER_ENDPOINT") or "").strip()
    token = (os.getenv("ZILLIZ_TOKEN") or "").strip()
    if not endpoint or not token:
        return {"reachable": False, "detail": "ZILLIZ_CLUSTER_ENDPOINT / ZILLIZ_TOKEN not set",
                "documents": None, "latency_s": None, "collection": None,
                "endpoint_host": None}

    from pymilvus import MilvusClient

    t0 = time.time()
    client = MilvusClient(uri=endpoint, token=token)
    collections = client.list_collections()
    latency = round(time.time() - t0, 3)

    collection = (os.getenv("ZILLIZ_COLLECTION_NAME") or "").strip()
    docs = None
    detail = f"connected; collections={collections}"
    if collection and collection in collections:
        try:
            stats = client.get_collection_stats(collection)
            docs = int(stats.get("row_count") or 0)
            detail = f"connected; {collection} row_count={docs}"
        except Exception as exc:  # stats can fail independently of connectivity
            detail = f"connected but stats failed for {collection}: {str(exc)[:160]}"
    elif collection:
        detail = f"connected but collection '{collection}' is absent (have: {collections})"

    return {"reachable": True, "detail": detail, "documents": docs,
            "latency_s": latency, "collection": collection,
            "endpoint_host": endpoint.split("//")[-1].split("/")[0]}


def refresh(force: bool = False) -> Dict[str, Any]:
    """Probe the configured store and cache the result. Never raises."""
    with _LOCK:
        last = _STATE.get("last_probe_ts")
        if not force and last and (time.time() - last) < 300:
            return dict(_STATE)

    try:
        import rag_config
        cloud_enabled = bool(getattr(rag_config, "CLOUD_MODE_ENABLED", False))
        collection = getattr(rag_config, "ZILLIZ_COLLECTION_NAME", None)
    except Exception as exc:
        with _LOCK:
            _STATE.update({"reachable": None, "detail": f"rag_config unavailable: {exc}",
                           "last_probe_ts": time.time()})
            return dict(_STATE)

    if not cloud_enabled:
        reason = ("CLOUD_MODE_ENABLED is false - the cloud vector store is never "
                  "attempted, so retrieval falls back to web search + model memory")
        try:
            import os
            has_creds = bool((os.getenv("ZILLIZ_CLUSTER_ENDPOINT") or "").strip()
                             and (os.getenv("ZILLIZ_TOKEN") or "").strip())
        except Exception:
            has_creds = False
        if has_creds:
            reason += " (credentials ARE present - enable the flag to use the corpus)"
        with _LOCK:
            _STATE.update({
                "mode": "disabled", "reachable": False, "detail": reason,
                "last_probe_ts": time.time(), "collection": collection,
                "endpoint_host": None, "documents": None, "latency_s": None,
            })
        logger.warning("[STORE-CHECK] %s", reason)
        return dict(_STATE)

    try:
        probe = _probe_cloud()
        mode = "cloud"
    except Exception as exc:
        probe = {"reachable": False, "detail": f"{type(exc).__name__}: {str(exc)[:220]}",
                 "documents": None, "latency_s": None, "collection": collection,
                 "endpoint_host": None}
        mode = "cloud"

    with _LOCK:
        _STATE.update({
            "mode": mode, "reachable": probe["reachable"], "detail": probe["detail"],
            "last_probe_ts": time.time(), "documents": probe.get("documents"),
            "latency_s": probe.get("latency_s"), "collection": probe.get("collection"),
            "endpoint_host": probe.get("endpoint_host"),
        })

    if probe["reachable"]:
        logger.info("[STORE-CHECK] vector store reachable: %s", probe["detail"])
        if probe.get("documents") is not None and probe["documents"] == 0:
            logger.warning("[STORE-CHECK] collection is EMPTY - the app will answer from "
                           "model memory and web fallback only")
    else:
        logger.error("[STORE-CHECK] VECTOR STORE UNREACHABLE: %s - answers will fall back "
                     "to web search + model memory", probe["detail"])
    return dict(_STATE)


def status() -> Dict[str, Any]:
    """Current known state without re-probing."""
    with _LOCK:
        return dict(_STATE)


def start_background_probe(delay_seconds: float = 5.0) -> None:
    """Probe shortly after boot so startup is not slowed by the network call."""

    def _run() -> None:
        try:
            time.sleep(max(0.0, delay_seconds))
            refresh(force=True)
        except Exception as exc:  # pragma: no cover
            logger.warning("[STORE-CHECK] background probe failed: %s", exc)

    threading.Thread(target=_run, name="store-check", daemon=True).start()