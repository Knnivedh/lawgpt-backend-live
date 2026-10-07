"""
AZURE SUPREME COURT LOCAL STORE
Cloud-connected fallback retriever that reads the Supreme Court corpus from
Azure App Service persistent storage (/home/data/...) using a compact manifest.
"""

from __future__ import annotations

import json
import logging
import os
import re
import time
import zipfile
from pathlib import Path
from typing import Dict, List, Optional

from rank_bm25 import BM25Okapi

try:
    from rag_system.core.sc_corpus_audit import (
        audit_supreme_court_corpus,
        compact_sc_audit_status,
    )
except Exception:
    try:
        from .sc_corpus_audit import audit_supreme_court_corpus, compact_sc_audit_status
    except Exception:
        audit_supreme_court_corpus = None  # type: ignore
        compact_sc_audit_status = None  # type: ignore

logger = logging.getLogger(__name__)


def _tokenize(text: str) -> List[str]:
    return re.findall(r"[a-z0-9]{3,}", (text or "").lower())


class AzureSupremeCourtStore:
    def __init__(
        self,
        root_dir: Optional[str] = None,
        manifest_relpath: str = "manifest/sc_case_manifest.json",
        zip_path: Optional[str] = None,
        zip_dir: Optional[str] = None,
    ):
        self.root_dir = Path(
            root_dir
            or os.getenv("SC_JUDGMENTS_CLOUD_ROOT", "/home/data/sc_judgments")
        )
        self.manifest_path = self.root_dir / manifest_relpath
        self.zip_path = Path(
            zip_path
            or os.getenv("SC_JUDGMENTS_CLOUD_ZIP", "/home/data/sc_judgments_cloud.zip")
        )
        self.zip_dir = Path(
            zip_dir
            or os.getenv("SC_JUDGMENTS_CLOUD_ZIP_DIR", "/home/data/sc_judgments_shards")
        )
        self.enabled = False
        self._cases: List[Dict] = []
        self._bm25: Optional[BM25Okapi] = None
        self._chunk_cache: Dict[str, List[Dict]] = {}
        self._zip_file: Optional[zipfile.ZipFile] = None
        self._zip_cache: Dict[str, zipfile.ZipFile] = {}
        self._diagnostics_cache: Optional[Dict] = None
        self._diagnostics_cache_at = 0.0
        self._init()

    def _init(self) -> None:
        try:
            if self.manifest_path.exists():
                manifest_text = self.manifest_path.read_text(encoding="utf-8")
            elif self.zip_path.exists():
                self._zip_file = zipfile.ZipFile(self.zip_path, "r")
                manifest_text = self._zip_file.read("manifest/sc_case_manifest.json").decode("utf-8")
            else:
                logger.warning(
                    f"[AZURE_SC] Manifest missing at {self.manifest_path} and zip missing at {self.zip_path}. Supreme Court fallback disabled."
                )
                return

            self._cases = json.loads(manifest_text)
            tokenized = [_tokenize(case.get("search_text", "")) for case in self._cases]
            self._bm25 = BM25Okapi(tokenized)
            self.enabled = True
            logger.info(
                f"[AZURE_SC] Loaded manifest with {len(self._cases):,} Supreme Court cases from {self.manifest_path}"
            )
        except Exception as exc:
            logger.error(f"[AZURE_SC] Failed to initialize Supreme Court manifest: {exc}")
            self.enabled = False

    def get_diagnostics(self, *, max_age_seconds: int = 600, deep: bool = False) -> Dict:
        now = time.time()
        if (
            self._diagnostics_cache is not None
            and not deep
            and now - self._diagnostics_cache_at < max_age_seconds
        ):
            return dict(self._diagnostics_cache)

        years = [
            int(str(case.get("year")))
            for case in self._cases
            if str(case.get("year", "")).isdigit()
        ]
        summary = {
            "enabled": self.enabled,
            "case_count": len(self._cases),
            "year_min": min(years) if years else None,
            "year_max": max(years) if years else None,
            "manifest_path": str(self.manifest_path),
            "zip_path": str(self.zip_path),
            "zip_dir": str(self.zip_dir),
            "audit": None,
        }

        if deep and audit_supreme_court_corpus is not None and compact_sc_audit_status is not None:
            try:
                audit = audit_supreme_court_corpus(
                    root_dir=self.root_dir,
                    zip_path=self.zip_path,
                    zip_dir=self.zip_dir,
                    check_local_files=self.manifest_path.exists(),
                    check_monolithic_zip=self.zip_path.exists(),
                    check_shard_zips=self.zip_dir.exists(),
                )
                summary["audit"] = compact_sc_audit_status(audit)
            except Exception as exc:
                summary["audit"] = {"ok": False, "errors": [str(exc)]}

        if not deep:
            self._diagnostics_cache = dict(summary)
            self._diagnostics_cache_at = now

        return summary

    def _load_chunks(self, chunks_relpath: str) -> List[Dict]:
        if chunks_relpath in self._chunk_cache:
            return self._chunk_cache[chunks_relpath]
        chunk_path = self.root_dir / chunks_relpath
        try:
            if chunk_path.exists():
                raw = chunk_path.read_text(encoding="utf-8")
            elif self._zip_file is not None:
                raw = self._zip_file.read(chunks_relpath.replace("\\", "/")).decode("utf-8")
            elif self.zip_dir.exists():
                year = chunks_relpath.replace("\\", "/").split("/")[1]
                try:
                    decade = f"{str(year)[:3]}0s"
                except Exception:
                    decade = "misc"
                shard_path = self.zip_dir / f"{decade}.zip"
                if shard_path.exists():
                    if str(shard_path) not in self._zip_cache:
                        self._zip_cache[str(shard_path)] = zipfile.ZipFile(shard_path, "r")
                    raw = self._zip_cache[str(shard_path)].read(chunks_relpath.replace("\\", "/")).decode("utf-8")
                else:
                    raise FileNotFoundError(str(shard_path))
            else:
                raise FileNotFoundError(str(chunk_path))
            chunks = json.loads(raw)
            if isinstance(chunks, list):
                self._chunk_cache[chunks_relpath] = chunks
                return chunks
        except Exception as exc:
            logger.warning(f"[AZURE_SC] Could not load chunk file {chunk_path}: {exc}")
        return []

    def _score_chunk(self, query_tokens: List[str], chunk: Dict) -> float:
        text = chunk.get("text", "")
        chunk_tokens = set(_tokenize(text))
        overlap = sum(1 for tok in query_tokens if tok in chunk_tokens)
        priority = str(chunk.get("priority", "")).lower()
        section = str(chunk.get("section", "")).lower()
        bonus = 0.0
        if priority == "high":
            bonus += 1.0
        if section in {"headnote", "arguments", "conclusion"}:
            bonus += 0.5
        return float(overlap) + bonus

    def search(self, query: str, n_results: int = 4) -> List[Dict]:
        if not self.enabled or not self._bm25:
            return []
        query_tokens = _tokenize(query)
        if not query_tokens:
            return []

        scores = self._bm25.get_scores(query_tokens)
        ranked_case_indices = sorted(
            range(len(scores)),
            key=lambda idx: scores[idx],
            reverse=True,
        )[: max(3, n_results)]

        hits: List[Dict] = []
        for case_idx in ranked_case_indices:
            case = self._cases[case_idx]
            case_score = float(scores[case_idx])
            if case_score <= 0:
                continue
            chunks = self._load_chunks(case["chunks_relpath"])
            ranked_chunks = sorted(
                chunks,
                key=lambda chunk: self._score_chunk(query_tokens, chunk),
                reverse=True,
            )[:2]
            for chunk in ranked_chunks:
                chunk_score = self._score_chunk(query_tokens, chunk)
                text = chunk.get("text", "")
                if not text:
                    continue
                hits.append(
                    {
                        "id": chunk.get("chunk_id") or case.get("case_id"),
                        "text": text,
                        "metadata": {
                            "title": case.get("case_name") or case.get("case_id"),
                            "case_name": case.get("case_name"),
                            "petitioner": case.get("petitioner"),
                            "respondent": case.get("respondent"),
                            "judgment_date": case.get("judgment_date"),
                            "year": case.get("year"),
                            "court": "Supreme Court of India",
                            "source": "SC_Judgments_FULL",
                            "source_store": "azure_sc_local",
                            "filename": case.get("filename"),
                            "case_id": case.get("case_id"),
                            "metadata_relpath": case.get("metadata_relpath"),
                            "chunks_relpath": case.get("chunks_relpath"),
                            "priority": chunk.get("priority"),
                            "section": chunk.get("section"),
                            "trusted_source": True,
                            "source_tier": "authoritative",
                            "source_locator": str(self.root_dir / case.get("chunks_relpath", "")),
                        },
                        "score": case_score + chunk_score,
                        "distance": 1 / max(case_score + chunk_score, 1.0),
                        "source": "azure_sc_local",
                    }
                )

        hits = sorted(hits, key=lambda item: item["score"], reverse=True)
        return hits[:n_results]
