"""Canonical authority resolver for Court Debate Elite.

The resolver is intentionally deterministic. It supplies known high-value
Indian-law authorities before the LLM drafts submissions, then optionally merges
retrieved source metadata when the retriever can prove a case.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple


PACK_PATH = Path(__file__).parent / "benchmark_inputs" / "court_authority_pack.json"


def _clean(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "")).strip()


def _slug(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", (value or "").lower()).strip("_") or "authority"


@dataclass(frozen=True)
class AuthorityRecord:
    authority_id: str
    canonical_name: str
    aliases: Tuple[str, ...]
    court: str
    year: str
    issues: Tuple[str, ...]
    article_or_statute_links: Tuple[str, ...]
    holding_summary: str
    limits_or_cautions: str
    remedy_relevance: str
    citation_status: str
    source_locator: str

    @classmethod
    def from_json(cls, data: Dict[str, Any]) -> "AuthorityRecord":
        return cls(
            authority_id=str(data["authority_id"]),
            canonical_name=str(data["canonical_name"]),
            aliases=tuple(str(item).lower() for item in data.get("aliases", [])),
            court=str(data.get("court", "")),
            year=str(data.get("year", "")),
            issues=tuple(str(item).lower() for item in data.get("issues", [])),
            article_or_statute_links=tuple(str(item) for item in data.get("article_or_statute_links", [])),
            holding_summary=str(data.get("holding_summary", "")),
            limits_or_cautions=str(data.get("limits_or_cautions", "")),
            remedy_relevance=str(data.get("remedy_relevance", "")),
            citation_status=str(data.get("citation_status", "canonical")),
            source_locator=str(data.get("source_locator", "")),
        )


class AuthorityResolver:
    def __init__(self, pack_path: Optional[Path] = None):
        self.pack_path = pack_path or PACK_PATH
        self.records = self._load_pack(self.pack_path)

    @staticmethod
    def _load_pack(path: Path) -> List[AuthorityRecord]:
        payload = json.loads(path.read_text(encoding="utf-8"))
        return [AuthorityRecord.from_json(item) for item in payload.get("authorities", [])]

    @staticmethod
    def _issue_text(user_query: str, issues: Sequence[Dict[str, Any]]) -> str:
        parts = [user_query or ""]
        for issue in issues:
            parts.append(str(issue.get("id", "")))
            parts.append(str(issue.get("bucket", "")))
            parts.append(str(issue.get("label", "")))
            parts.append(str(issue.get("question", "")))
        return " ".join(parts).lower()

    @staticmethod
    def _record_matches(record: AuthorityRecord, haystack: str) -> bool:
        if any(alias and alias in haystack for alias in record.aliases):
            return True
        return any(issue.replace("_", " ") in haystack or issue in haystack for issue in record.issues)

    def match(self, user_query: str, issues: Sequence[Dict[str, Any]]) -> List[AuthorityRecord]:
        haystack = self._issue_text(user_query, issues)
        matched = [record for record in self.records if self._record_matches(record, haystack)]
        if any(term in haystack for term in ("hijab", "interfaith", "habeas", "love jihad", "religious identifiers")):
            priority_ids = {
                "privacy_puttaswamy",
                "adult_marriage_shafin_jahan",
                "adult_choice_lata_singh",
                "religion_bijoe_emmanuel",
                "religion_shirur_mutt",
                "religion_sabarimala",
                "hijab_aishat_shifa_resham",
                "proportionality_modern_dental",
                "criminal_process_lalita_kumari",
                "criminal_quashing_bhajan_lal",
            }
            by_id = {record.authority_id: record for record in self.records}
            for authority_id in priority_ids:
                record = by_id.get(authority_id)
                if record and record not in matched:
                    matched.append(record)
        return matched

    @staticmethod
    def _doc_identity_text(doc: Dict[str, Any]) -> str:
        meta = doc.get("metadata") or {}
        values = [
            doc.get("text", ""),
            doc.get("source", ""),
            doc.get("title", ""),
            meta.get("title", ""),
            meta.get("case_name", ""),
            meta.get("case_id", ""),
            meta.get("source", ""),
            meta.get("filename", ""),
        ]
        return " ".join(str(value) for value in values).lower()

    @classmethod
    def _doc_supports_record(cls, doc: Dict[str, Any], record: AuthorityRecord) -> bool:
        identity = cls._doc_identity_text(doc)
        return any(alias and alias in identity for alias in record.aliases)

    @staticmethod
    def _canonical_row(record: AuthorityRecord, issue_link: str, status: str = "canonical") -> Dict[str, Any]:
        return {
            "id": record.authority_id,
            "display_name": record.canonical_name,
            "domain": issue_link,
            "status": status,
            "title": record.canonical_name,
            "court": record.court,
            "year": record.year,
            "source": record.source_locator,
            "source_store": "court_authority_pack",
            "source_tier": "canonical",
            "case_id": record.authority_id,
            "case_name": record.canonical_name,
            "issue_link": issue_link,
            "use_in_debate": "Use as canonical authority anchor; verify source text for direct quotation.",
            "extract": record.holding_summary,
            "holding_summary": record.holding_summary,
            "limits_or_cautions": record.limits_or_cautions,
            "remedy_relevance": record.remedy_relevance,
            "citation_status": record.citation_status,
            "source_locator": record.source_locator,
            "aliases": list(record.aliases),
        }

    @staticmethod
    def _retrieved_row(record: AuthorityRecord, doc: Dict[str, Any], issue_link: str) -> Dict[str, Any]:
        meta = doc.get("metadata") or {}
        row = AuthorityResolver._canonical_row(record, issue_link, status="retrieved")
        row.update(
            {
                "title": meta.get("title") or meta.get("case_name") or record.canonical_name,
                "court": meta.get("court") or record.court,
                "year": str(meta.get("year") or record.year),
                "source": meta.get("source") or doc.get("source") or record.source_locator,
                "source_store": meta.get("source_store") or "retriever",
                "source_tier": meta.get("source_tier") or "retrieved",
                "case_id": meta.get("case_id") or record.authority_id,
                "case_name": meta.get("case_name") or record.canonical_name,
                "filename": meta.get("filename", ""),
                "url": meta.get("url") or doc.get("url", ""),
                "score": doc.get("score", ""),
                "extract": _clean(doc.get("text") or record.holding_summary)[:600],
            }
        )
        return row

    def build_bundle(
        self,
        user_query: str,
        issues: Sequence[Dict[str, Any]],
        retrieved_docs: Optional[Iterable[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        matched = self.match(user_query, issues)
        docs = list(retrieved_docs or [])
        rows: List[Dict[str, Any]] = []
        gaps: List[Dict[str, Any]] = []
        for record in matched:
            issue_link = ", ".join(record.issues[:4]) or "general"
            supporting_doc = next((doc for doc in docs if self._doc_supports_record(doc, record)), None)
            if supporting_doc:
                row = self._retrieved_row(record, supporting_doc, issue_link)
            else:
                row = self._canonical_row(record, issue_link, status="canonical")
            rows.append(row)
            if row["status"] != "retrieved":
                gaps.append(row)

        return {
            "verified_authorities": rows,
            "authority_gaps": gaps,
            "unsupported_mentions": [],
            "issue_authority_matrix": self._issue_authority_matrix(issues, rows),
            "remedy_authority_matrix": self._remedy_authority_matrix(rows),
        }

    @staticmethod
    def _issue_authority_matrix(issues: Sequence[Dict[str, Any]], rows: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
        matrix: List[Dict[str, Any]] = []
        for issue in issues:
            text = f"{issue.get('id', '')} {issue.get('label', '')} {issue.get('question', '')}".lower()
            linked = [
                row["display_name"]
                for row in rows
                if any(alias in text for alias in row.get("aliases", []))
                or any(tag.replace("_", " ") in text for tag in str(row.get("issue_link", "")).split(", "))
            ]
            if not linked:
                linked = [row["display_name"] for row in rows[:3]]
            matrix.append(
                {
                    "issue_id": issue.get("id", ""),
                    "issue_label": issue.get("label", ""),
                    "authorities": linked[:5],
                }
            )
        return matrix

    @staticmethod
    def _remedy_authority_matrix(rows: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
        return [
            {
                "authority": row["display_name"],
                "remedy_relevance": row.get("remedy_relevance", ""),
            }
            for row in rows
            if row.get("remedy_relevance")
        ]


def normalize_authority_display_name(title: str, case_name: str = "", fallback: str = "") -> str:
    value = _clean(case_name or title or fallback)
    if re.fullmatch(r"batch[_\-\s]*\d+(?:[_\-\s]*\d+)?", value.lower()):
        return _clean(fallback) or "Unknown authority"
    return value or "Unknown authority"
