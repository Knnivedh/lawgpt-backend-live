import json
import sys
import zipfile
from pathlib import Path


project_root = Path(__file__).parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from rag_system.core.sc_corpus_audit import audit_supreme_court_corpus
from kaanoon_test.advanced_rag_api_server import format_rag_response


def _write_case(root: Path, year: str, case_id: str) -> dict:
    metadata_dir = root / "metadata" / year
    chunks_dir = root / "chunks" / year
    metadata_dir.mkdir(parents=True, exist_ok=True)
    chunks_dir.mkdir(parents=True, exist_ok=True)

    metadata = {
        "case_id": case_id,
        "case_name": "Justice K S Puttaswamy v Union of India",
        "year": year,
        "filename": f"{case_id}.txt",
    }
    chunks = [
        {
            "chunk_id": f"{case_id}_chunk_0000",
            "text": "Right to privacy under Article 21 in Puttaswamy.",
            "priority": "high",
            "section": "headnote",
        }
    ]
    meta_rel = f"metadata/{year}/{case_id}_meta.json"
    chunks_rel = f"chunks/{year}/{case_id}_chunks.json"
    (root / meta_rel).write_text(json.dumps(metadata), encoding="utf-8")
    (root / chunks_rel).write_text(json.dumps(chunks), encoding="utf-8")
    return {
        **metadata,
        "chunks_relpath": chunks_rel,
        "metadata_relpath": meta_rel,
        "search_text": "Puttaswamy privacy Article 21",
    }


def test_sc_corpus_audit_detects_manifest_zip_and_shard_parity(tmp_path):
    root = tmp_path / "SC_Judgments_FULL"
    manifest_dir = root / "manifest"
    manifest_dir.mkdir(parents=True)
    record = _write_case(root, "2017", "puttaswamy_2017")
    (manifest_dir / "sc_case_manifest.json").write_text(
        json.dumps([record]),
        encoding="utf-8",
    )

    zip_path = tmp_path / "sc_judgments_cloud.zip"
    with zipfile.ZipFile(zip_path, "w") as zf:
        for rel in ("manifest/sc_case_manifest.json", record["chunks_relpath"]):
            zf.write(root / rel, rel)

    shard_dir = tmp_path / "sc_shards"
    shard_dir.mkdir()
    with zipfile.ZipFile(shard_dir / "2010s.zip", "w") as zf:
        zf.write(root / record["chunks_relpath"], record["chunks_relpath"])

    report = audit_supreme_court_corpus(
        root_dir=root,
        zip_path=zip_path,
        zip_dir=shard_dir,
    )

    assert report["ok"] is True
    assert report["case_count"] == 1
    assert report["year_min"] == 2017
    assert report["local"]["missing_chunk_count"] == 0
    assert report["monolithic_zip"]["missing_chunk_count"] == 0
    assert report["shard_zips"]["missing_chunk_count"] == 0


def test_sc_corpus_audit_reports_missing_packaged_chunks(tmp_path):
    root = tmp_path / "SC_Judgments_FULL"
    manifest_dir = root / "manifest"
    manifest_dir.mkdir(parents=True)
    record = _write_case(root, "2017", "puttaswamy_2017")
    (manifest_dir / "sc_case_manifest.json").write_text(
        json.dumps([record]),
        encoding="utf-8",
    )

    zip_path = tmp_path / "sc_judgments_cloud.zip"
    with zipfile.ZipFile(zip_path, "w") as zf:
        zf.write(root / "manifest/sc_case_manifest.json", "manifest/sc_case_manifest.json")

    report = audit_supreme_court_corpus(
        root_dir=root,
        zip_path=zip_path,
        zip_dir=tmp_path / "missing_shards",
        check_shard_zips=False,
    )

    assert report["ok"] is False
    assert report["monolithic_zip"]["missing_chunk_count"] == 1
    assert report["monolithic_zip"]["missing_chunk_examples"] == [record["chunks_relpath"]]


def test_format_rag_response_preserves_source_identity_metadata():
    result = {
        "answer": "Puttaswamy recognizes privacy as part of Article 21. This is a grounded test answer.",
        "source_documents": [
            {
                "id": "puttaswamy_2017_chunk_0000",
                "text": "Justice K S Puttaswamy v Union of India privacy extract.",
                "source": "azure_sc_local",
                "metadata": {
                    "case_id": "puttaswamy_2017",
                    "case_name": "Justice K S Puttaswamy v Union of India",
                    "year": 2017,
                    "court": "Supreme Court of India",
                    "source_store": "azure_sc_local",
                    "source_tier": "authoritative",
                    "filename": "puttaswamy.txt",
                    "chunks_relpath": "chunks/2017/puttaswamy_2017_chunks.json",
                    "trusted_source": True,
                },
            }
        ],
        "metadata": {
            "strategy": "academic_direct",
            "grounding": {
                "total_sources": 1,
                "trusted_sources": 1,
            },
        },
    }

    formatted = format_rag_response(result, "metadata-test", question_hint="privacy")
    source = formatted["sources"][0]

    assert source["case_id"] == "puttaswamy_2017"
    assert source["case_name"] == "Justice K S Puttaswamy v Union of India"
    assert source["year"] == 2017
    assert source["court"] == "Supreme Court of India"
    assert source["source_store"] == "azure_sc_local"
    assert source["source_tier"] == "authoritative"
    assert source["trusted_source"] is True
