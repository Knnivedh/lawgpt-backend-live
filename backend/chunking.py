# chunking.py
"""
Split each source item into one parent record and several child chunks
(hierarchical RAG: search the children, hand the generator the parent).

Chunk sizes are measured with the EMBEDDING MODEL's own tokenizer. The model
reads at most 512 tokens and silently drops the rest, so a chunk plus its
title must fit inside that. (An earlier version sized chunks with OpenAI's
cl100k tokenizer and embedded the whole question in front of every chunk;
11% of chunks ended up embedded as the question alone.)

Children per item:
  - the question / summary text, split into chunks   (kind "question")
  - each expert response, split into chunks          (kind "answer")
The title is NOT stored in the child text; embedding.py prepends it.

Paths can be overridden with DATA_DIR and CHUNKED_DIR.
"""
import json
import os

from tokenizers import Tokenizer
from tqdm import tqdm

DATA_DIR = os.getenv("DATA_DIR", "./data/family_law_domain")
OUTPUT_DIR = os.getenv("CHUNKED_DIR", "./data/chunked")
os.makedirs(OUTPUT_DIR, exist_ok=True)

EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "bhavyagiri/InLegal-Sbert")
MODEL_MAX_TOKENS = 512
TITLE_MAX_TOKENS = 40    # embedding.py prepends the title to every child
CHUNK_SIZE = 400         # model tokens; 2 specials + 40 title + 400 chunk + separator < 512
CHUNK_OVERLAP = 60

# Milvus VARCHAR limits (see milvus_store.py). Parents are stored whole; the
# retriever trims long parents around the matched passage at query time.
PARENT_MAX_CHARS = 60000
QUERY_TEXT_MAX_CHARS = 9000

TOKENIZER = Tokenizer.from_pretrained(EMBEDDING_MODEL)
TOKENIZER.no_truncation()


def count_tokens(text):
    return len(TOKENIZER.encode(text, add_special_tokens=False).ids)


def chunk_text(text, chunk_size=CHUNK_SIZE, overlap=CHUNK_OVERLAP):
    """Split text into windows of at most chunk_size model tokens.

    Slices the original string by token character offsets, so chunk text is
    always an exact substring of the input (and therefore of the parent).
    """
    offsets = TOKENIZER.encode(text, add_special_tokens=False).offsets
    if not offsets:
        return []

    chunks = []
    start = 0
    while start < len(offsets):
        end = min(start + chunk_size, len(offsets))
        chunk = text[offsets[start][0]:offsets[end - 1][1]].strip()
        if chunk:
            chunks.append(chunk)
        if end == len(offsets):
            break
        start += chunk_size - overlap
    return chunks


def process_category_file(file_path, id_offset=0):
    """Process one JSON file and write its parent and child records.

    id_offset shifts parent_id past every item already assigned by files
    processed earlier in this run. Without it, each file's item index resets
    to 0, so different files collide on the same parent_id — and retrieval's
    parent-expansion lookup (by parent_id alone) can silently return the
    wrong file's parent record. Returns len(data) so the caller can advance
    the offset for the next file.
    """
    category_name = os.path.basename(file_path).replace(".json", "")
    output_file = os.path.join(OUTPUT_DIR, f"{category_name}_chunks.json")

    with open(file_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    chunks_list = []
    chunk_id = 0
    skipped = 0

    print(f"\n📋 Processing {len(data)} items from {category_name} (parent_id offset {id_offset})")

    for local_idx, item in enumerate(tqdm(data, desc=f"Chunking {category_name}")):
        item_idx = id_offset + local_idx
        query_text = (item.get("query-text") or "").strip()
        responses = item.get("responses") or []
        if not isinstance(responses, list):
            responses = []
        title = (item.get("query-title") or "")[:500]
        citations = item.get("citations") or []
        url = (item.get("query-url") or "")[:500]

        response_texts = [
            f"Expert {resp.get('responder', 'Expert')}: {resp.get('response-text', '').strip()}"
            for resp in responses
            if (resp.get("response-text") or "").strip()
        ]
        parent_text = "\n\n".join([query_text] + response_texts).strip()
        if not parent_text:
            skipped += 1
            continue

        def record(content, is_parent, kind):
            nonlocal chunk_id
            chunks_list.append({
                "content": content,
                "metadata": {
                    "parent_id": item_idx,
                    "chunk_id": chunk_id,
                    "title": title,
                    "query-text": query_text[:QUERY_TEXT_MAX_CHARS],
                    "citations": citations,
                    "url": url,
                    "is_parent": is_parent,
                    "kind": kind,
                },
            })
            chunk_id += 1

        # Parent: the complete item (question + every response).
        record(parent_text[:PARENT_MAX_CHARS], True, "parent")

        # Children: the question itself, then each response.
        for piece in chunk_text(query_text):
            record(piece, False, "question")
        for response_text in response_texts:
            for piece in chunk_text(response_text):
                record(piece, False, "answer")

    with open(output_file, "w", encoding="utf-8") as out:
        json.dump(chunks_list, out, indent=2, ensure_ascii=False)

    parents = sum(1 for c in chunks_list if c["metadata"]["is_parent"])
    print(f"✅ Saved {len(chunks_list)} records ({parents} parents, {len(chunks_list) - parents} children) → {output_file}")
    if skipped:
        print(f"⚠️  Skipped {skipped} empty items (no question text and no responses)")

    return len(data)


if __name__ == "__main__":
    json_files = sorted(f for f in os.listdir(DATA_DIR) if f.endswith(".json") and not f.endswith(".bak"))

    if not json_files:
        print("❌ No JSON files found in", DATA_DIR)
        exit(1)

    print(f"Found {len(json_files)} JSON files to process")

    parent_id_offset = 0
    for filename in json_files:
        item_count = process_category_file(os.path.join(DATA_DIR, filename), id_offset=parent_id_offset)
        parent_id_offset += item_count

    print("\n🎯 All categories chunked and saved under:", OUTPUT_DIR)
    print(f"📊 Chunks sized with the {EMBEDDING_MODEL} tokenizer: {CHUNK_SIZE} tokens, {CHUNK_OVERLAP} overlap")
