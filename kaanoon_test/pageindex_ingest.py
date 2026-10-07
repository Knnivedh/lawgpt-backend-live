"""
PageIndex Statute Ingestion Script
===================================
Indexes all Indian statute files into PageIndex cloud so they can be
queried by PageIndexRetriever at runtime.

Usage:
    python pageindex_ingest.py                  # index all new files
    python pageindex_ingest.py --force          # re-index everything
    python pageindex_ingest.py --list           # list indexed docs
    python pageindex_ingest.py --file foo.txt   # index single file

Requirements:
    pip install pageindex
    Set PAGEINDEX_API_KEY in config/.env or environment.

After running, registry is saved to:
    kaanoon_test/pageindex_doc_registry.json
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
STATUTES_DIR = ROOT / "BACKUP_DATA" / "DATA" / "Statutes"
REGISTRY_PATH = ROOT / "LAW-GPT_new" / "LAW-GPT" / "kaanoon_test" / "pageindex_doc_registry.json"
ENV_PATH = ROOT / "LAW-GPT_new" / "LAW-GPT" / "config" / ".env"

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s", datefmt="%H:%M:%S")
logger = logging.getLogger("pageindex_ingest")

SUPPORTED_EXT = {".txt", ".pdf"}

PRIORITY_NAMES = [
    "Bharatiya_Nyaya_Sanhita",
    "Consumer_Protection_Act",
    "Indian_Contract_Act",
    "Code_of_Civil_Procedure",
    "Indian_Penal_Code",
    "Bharatiya_Nagarik_Suraksha_Sanhita",
    "Bharatiya_Sakshya_Adhiniyam",
    "Transfer_of_Property_Act",
    "Specific_Relief_Act",
    "Sale_of_Goods_Act",
    "Insolvency_and_Bankruptcy_Code",
    "Competition_Act",
]


def load_env(env_path: Path) -> None:
    if not env_path.exists():
        return
    with open(env_path, "r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, val = line.partition("=")
            if key.strip() and key.strip() not in os.environ:
                os.environ[key.strip()] = val.strip().strip('"').strip("'")


def load_registry(registry_path: Path) -> dict:
    if registry_path.exists():
        try:
            with open(registry_path, "r", encoding="utf-8") as fh:
                return json.load(fh)
        except Exception as e:
            logger.warning(f"Could not read registry: {e}")
    return {}


def save_registry(registry: dict, registry_path: Path) -> None:
    registry_path.parent.mkdir(parents=True, exist_ok=True)
    with open(registry_path, "w", encoding="utf-8") as fh:
        json.dump(registry, fh, indent=2, ensure_ascii=False)
    logger.info(f"Registry saved -> {registry_path}")


def wait_until_ready(client, doc_id: str, timeout: int = 300, poll: int = 10) -> bool:
    deadline = time.time() + timeout
    dots = 0
    while time.time() < deadline:
        try:
            if client.is_retrieval_ready(doc_id):
                return True
        except Exception:
            pass
        dots += 1
        print(f"\r  Waiting{'.' * (dots % 4)}   ", end="", flush=True)
        time.sleep(poll)
    print()
    return False


def collect_statute_files(directory: Path) -> list:
    if not directory.exists():
        logger.error(f"Statutes directory not found: {directory}")
        return []
    all_files = [f for f in directory.iterdir()
                 if f.is_file() and f.suffix.lower() in SUPPORTED_EXT]
    def priority_key(p: Path) -> int:
        stem = p.stem
        for i, name in enumerate(PRIORITY_NAMES):
            if name.lower() in stem.lower():
                return i
        return len(PRIORITY_NAMES)
    return sorted(all_files, key=priority_key)


def index_files(files: list, registry: dict, client, force: bool = False) -> dict:
    total = len(files)
    success = 0
    skipped = 0
    failed = 0
    for i, fpath in enumerate(files, 1):
        doc_name = fpath.stem
        print(f"\n[{i}/{total}] {doc_name}")
        print(f"  File : {fpath.name}  ({fpath.stat().st_size // 1024} KB)")
        if doc_name in registry and not force:
            print(f"  Already indexed -> doc_id={registry[doc_name]}")
            skipped += 1
            continue
        try:
            print(f"  Submitting to PageIndex ...")
            result = client.submit_document(file_path=str(fpath))
            doc_id = result.get("doc_id") or result.get("id") or result.get("document_id")
            if not doc_id:
                logger.error(f"  No doc_id in response: {result}")
                failed += 1
                continue
            print(f"  doc_id={doc_id}  Waiting for indexing ...")
            ready = wait_until_ready(client, doc_id, timeout=300, poll=10)
            if not ready:
                logger.error(f"  Timed out waiting for '{doc_name}'")
                failed += 1
                continue
            registry[doc_name] = doc_id
            save_registry(registry, REGISTRY_PATH)
            print(f"  Indexed successfully")
            success += 1
        except Exception as exc:
            logger.error(f"  Failed: {exc}")
            failed += 1
    print(f"\n{'='*55}")
    print(f"INGESTION COMPLETE")
    print(f"  Indexed  : {success}")
    print(f"  Skipped  : {skipped}")
    print(f"  Failed   : {failed}")
    print(f"  Registry : {REGISTRY_PATH}")
    print(f"{'='*55}")
    return registry


def cmd_list(registry: dict) -> None:
    if not registry:
        print("No documents indexed yet.")
        return
    print(f"\n{'='*55}")
    print(f"INDEXED DOCUMENTS ({len(registry)} total)")
    print(f"{'='*55}")
    for i, (name, doc_id) in enumerate(registry.items(), 1):
        print(f"  {i:2d}. {name}")
        print(f"      doc_id: {doc_id}")
    print(f"{'='*55}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Index Indian statute files into PageIndex cloud.")
    parser.add_argument("--force", action="store_true", help="Re-index documents even if already in registry")
    parser.add_argument("--list", action="store_true", help="List already-indexed documents and exit")
    parser.add_argument("--file", type=str, default=None, help="Index a single specific file")
    parser.add_argument("--statutes-dir", type=str, default=str(STATUTES_DIR),
                        help=f"Override statutes directory")
    args = parser.parse_args()
    load_env(ENV_PATH)
    api_key = os.getenv("PAGEINDEX_API_KEY", "")
    if not api_key:
        print("\n  PAGEINDEX_API_KEY not set!")
        print("    Get your key at: https://dash.pageindex.ai/api-keys")
        print(f"    Then add to    : {ENV_PATH}")
        sys.exit(1)
    try:
        from pageindex import PageIndexClient
    except ImportError:
        print("\n  'pageindex' package not installed!")
        print("    Run: pip install pageindex")
        sys.exit(1)
    registry = load_registry(REGISTRY_PATH)
    if args.list:
        cmd_list(registry)
        return
    client = PageIndexClient(api_key=api_key)
    logger.info(f"PageIndex client created (key=...{api_key[-6:]})")
    statutes_dir = Path(args.statutes_dir)
    if args.file:
        f = Path(args.file)
        if not f.is_absolute():
            candidate = statutes_dir / args.file
            if candidate.exists():
                f = candidate
        if not f.exists():
            print(f"File not found: {args.file}")
            sys.exit(1)
        files = [f]
    else:
        files = collect_statute_files(statutes_dir)
        if not files:
            print(f"No statute files found in: {statutes_dir}")
            sys.exit(1)
        print(f"\nFound {len(files)} statute files in: {statutes_dir}")
    index_files(files, registry, client, force=args.force)


if __name__ == "__main__":
    main()