"""
Read-only Supreme Court corpus audit helpers.

These functions intentionally avoid mutating files or rebuilding indexes. They
verify that the current manifest, local chunks, monolithic zip, and shard zips
agree with each other so deployment can prove the SC fallback corpus is usable.
"""

from __future__ import annotations

import json
import zipfile
from collections import Counter
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Set


DEFAULT_MANIFEST_RELPATH = "manifest/sc_case_manifest.json"


def _safe_read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _norm_relpath(value: str) -> str:
    return str(value or "").replace("\\", "/").lstrip("/")


def _decade_zip_name(chunks_relpath: str) -> str:
    parts = _norm_relpath(chunks_relpath).split("/")
    year = parts[1] if len(parts) > 1 else "misc"
    if len(str(year)) >= 4 and str(year)[:4].isdigit():
        return f"{str(year)[:3]}0s.zip"
    return "misc.zip"


def _zip_names(path: Path) -> Set[str]:
    with zipfile.ZipFile(path, "r") as zf:
        return {_norm_relpath(name) for name in zf.namelist()}


def _load_manifest(
    root_dir: Path,
    manifest_relpath: str = DEFAULT_MANIFEST_RELPATH,
    zip_path: Optional[Path] = None,
) -> tuple[List[Dict[str, Any]], str]:
    manifest_path = root_dir / manifest_relpath
    if manifest_path.exists():
        return _safe_read_json(manifest_path), str(manifest_path)

    if zip_path and zip_path.exists():
        with zipfile.ZipFile(zip_path, "r") as zf:
            manifest = json.loads(zf.read(_norm_relpath(manifest_relpath)).decode("utf-8"))
        return manifest, str(zip_path) + "!" + _norm_relpath(manifest_relpath)

    raise FileNotFoundError(
        f"SC manifest not found at {manifest_path}"
        + (f" or {zip_path}" if zip_path else "")
    )


def audit_supreme_court_corpus(
    *,
    root_dir: Path,
    manifest_relpath: str = DEFAULT_MANIFEST_RELPATH,
    zip_path: Optional[Path] = None,
    zip_dir: Optional[Path] = None,
    check_local_files: bool = True,
    check_monolithic_zip: bool = True,
    check_shard_zips: bool = True,
    max_examples: int = 20,
) -> Dict[str, Any]:
    """Return a compact integrity report for the SC corpus."""

    root_dir = Path(root_dir)
    zip_path = Path(zip_path) if zip_path else None
    zip_dir = Path(zip_dir) if zip_dir else None

    report: Dict[str, Any] = {
        "root_dir": str(root_dir),
        "manifest_relpath": manifest_relpath,
        "zip_path": str(zip_path) if zip_path else None,
        "zip_dir": str(zip_dir) if zip_dir else None,
        "manifest_found": False,
        "ok": False,
        "errors": [],
    }

    try:
        manifest, manifest_source = _load_manifest(root_dir, manifest_relpath, zip_path)
    except Exception as exc:
        report["errors"].append(str(exc))
        return report

    if not isinstance(manifest, list):
        report["errors"].append("Manifest is not a JSON list")
        return report

    case_ids = [str(item.get("case_id") or "").strip() for item in manifest]
    valid_case_ids = [case_id for case_id in case_ids if case_id]
    dupes = sorted([case_id for case_id, count in Counter(valid_case_ids).items() if count > 1])
    years = [
        int(str(item.get("year")))
        for item in manifest
        if str(item.get("year", "")).isdigit()
    ]
    chunk_relpaths = [
        _norm_relpath(item.get("chunks_relpath", ""))
        for item in manifest
        if item.get("chunks_relpath")
    ]
    metadata_relpaths = [
        _norm_relpath(item.get("metadata_relpath", ""))
        for item in manifest
        if item.get("metadata_relpath")
    ]

    report.update(
        {
            "manifest_found": True,
            "manifest_source": manifest_source,
            "case_count": len(manifest),
            "unique_case_ids": len(set(valid_case_ids)),
            "duplicate_case_ids": dupes[:max_examples],
            "duplicate_case_id_count": len(dupes),
            "year_min": min(years) if years else None,
            "year_max": max(years) if years else None,
            "chunk_relpath_count": len(chunk_relpaths),
            "metadata_relpath_count": len(metadata_relpaths),
            "local": {},
            "monolithic_zip": {},
            "shard_zips": {},
        }
    )

    if check_local_files:
        missing_chunks = [rel for rel in chunk_relpaths if not (root_dir / rel).exists()]
        missing_metadata = [rel for rel in metadata_relpaths if not (root_dir / rel).exists()]
        report["local"] = {
            "checked": True,
            "missing_chunk_count": len(missing_chunks),
            "missing_metadata_count": len(missing_metadata),
            "missing_chunk_examples": missing_chunks[:max_examples],
            "missing_metadata_examples": missing_metadata[:max_examples],
        }
    else:
        report["local"] = {"checked": False}

    if check_monolithic_zip:
        if zip_path and zip_path.exists():
            names = _zip_names(zip_path)
            missing_zip_chunks = [rel for rel in chunk_relpaths if rel not in names]
            report["monolithic_zip"] = {
                "checked": True,
                "exists": True,
                "entry_count": len(names),
                "has_manifest": _norm_relpath(manifest_relpath) in names,
                "chunk_entry_count": sum(
                    1 for name in names if name.startswith("chunks/") and name.endswith(".json")
                ),
                "missing_chunk_count": len(missing_zip_chunks),
                "missing_chunk_examples": missing_zip_chunks[:max_examples],
            }
        else:
            report["monolithic_zip"] = {
                "checked": True,
                "exists": False,
                "missing_chunk_count": len(chunk_relpaths),
            }
    else:
        report["monolithic_zip"] = {"checked": False}

    if check_shard_zips:
        if zip_dir and zip_dir.exists():
            shard_names_cache: Dict[str, Set[str]] = {}
            missing_shard_chunks = []
            missing_shard_files = set()
            for rel in chunk_relpaths:
                shard_name = _decade_zip_name(rel)
                shard_path = zip_dir / shard_name
                if not shard_path.exists():
                    missing_shard_files.add(shard_name)
                    missing_shard_chunks.append(rel)
                    continue
                if shard_name not in shard_names_cache:
                    shard_names_cache[shard_name] = _zip_names(shard_path)
                if rel not in shard_names_cache[shard_name]:
                    missing_shard_chunks.append(rel)
            report["shard_zips"] = {
                "checked": True,
                "exists": True,
                "shard_count": len(list(zip_dir.glob("*.zip"))),
                "missing_shard_files": sorted(missing_shard_files)[:max_examples],
                "missing_shard_file_count": len(missing_shard_files),
                "missing_chunk_count": len(missing_shard_chunks),
                "missing_chunk_examples": missing_shard_chunks[:max_examples],
            }
        else:
            report["shard_zips"] = {
                "checked": True,
                "exists": False,
                "missing_chunk_count": len(chunk_relpaths),
            }
    else:
        report["shard_zips"] = {"checked": False}

    failure_counts = [
        report["duplicate_case_id_count"],
        report.get("local", {}).get("missing_chunk_count", 0),
        report.get("local", {}).get("missing_metadata_count", 0),
        report.get("monolithic_zip", {}).get("missing_chunk_count", 0),
        report.get("shard_zips", {}).get("missing_chunk_count", 0),
        report.get("shard_zips", {}).get("missing_shard_file_count", 0),
    ]
    report["ok"] = not report["errors"] and all(count == 0 for count in failure_counts)
    return report


def compact_sc_audit_status(report: Dict[str, Any]) -> Dict[str, Any]:
    """Return health-payload-safe summary fields."""

    return {
        "ok": bool(report.get("ok")),
        "case_count": report.get("case_count", 0),
        "year_min": report.get("year_min"),
        "year_max": report.get("year_max"),
        "duplicate_case_id_count": report.get("duplicate_case_id_count", 0),
        "local_missing_chunk_count": report.get("local", {}).get("missing_chunk_count"),
        "local_missing_metadata_count": report.get("local", {}).get("missing_metadata_count"),
        "monolithic_zip_missing_chunk_count": report.get("monolithic_zip", {}).get("missing_chunk_count"),
        "shard_zip_missing_chunk_count": report.get("shard_zips", {}).get("missing_chunk_count"),
        "errors": report.get("errors", [])[:3],
    }
