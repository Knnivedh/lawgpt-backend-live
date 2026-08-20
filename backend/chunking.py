# chunking.py
import os
import json
import tiktoken
from tqdm import tqdm

# Define constants
DATA_DIR = "./data/family_law_domain"
OUTPUT_DIR = "./data/chunked"
os.makedirs(OUTPUT_DIR, exist_ok=True)

# Configure tokenization
ENCODER = tiktoken.get_encoding("cl100k_base")  # same as OpenAI models
CHUNK_SIZE = 600  # Reduced from 800 to prevent overflow with longer embeddings
CHUNK_OVERLAP = 80  # Reduced proportionally
MAX_QUERY_LENGTH = 8000  # Reduced from 9000 for safety

# Hierarchical RAG: each Q&A item also gets one "parent" record holding its
# full combined text (query + all expert responses), so retrieval can expand
# a matched child chunk back to complete, ungrounded-free context.
PARENT_MAX_TOKENS = 1800

def tokenize_text(text):
    """Convert text into tokens."""
    return ENCODER.encode(text)

def detokenize_text(tokens):
    """Convert tokens back to text."""
    return ENCODER.decode(tokens)

def chunk_text(text, chunk_size=CHUNK_SIZE, overlap=CHUNK_OVERLAP):
    """Token-based chunking with overlap - optimized to prevent overflow."""
    tokens = tokenize_text(text)
    chunks = []
    start = 0
    
    # Ensure we don't create chunks that are too large
    while start < len(tokens):
        end = min(start + chunk_size, len(tokens))
        chunk = detokenize_text(tokens[start:end])
        
        # Verify chunk is not empty
        if chunk.strip():
            chunks.append(chunk)
        
        # Move to next chunk with overlap
        start += chunk_size - overlap
        
        # Prevent infinite loop for very small texts
        if end == len(tokens):
            break
    
    return chunks

def process_category_file(file_path, id_offset=0):
    """Process one JSON file and create chunks in the required format.

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
    overflow_count = 0

    print(f"\n📋 Processing {len(data)} items from {category_name} (parent_id offset {id_offset})")

    for local_idx, item in enumerate(tqdm(data, desc=f"Chunking {category_name}")):
        item_idx = id_offset + local_idx
        query_text = item.get("query-text", "").strip()
        
        # Truncate query text if too long
        if len(query_text) > MAX_QUERY_LENGTH:
            query_text = query_text[:MAX_QUERY_LENGTH]
            overflow_count += 1
            
        responses = item.get("responses", [])
        title = item.get("query-title", "")[:500]  # Limit title length
        citations = item.get("citations", [])
        url = item.get("query-url", "")[:500]  # Limit URL length

        # --- Parent record: full combined text for this Q&A item ---
        # Used at retrieval time to expand a matched child chunk back to
        # its complete original context (small-to-big retrieval).
        combined_responses = "\n\n".join(
            f"Expert {resp.get('responder', 'Expert')}: {resp.get('response-text', '').strip()}"
            for resp in responses
            if resp.get("response-text", "").strip()
        )
        parent_text = f"{query_text}\n\n{combined_responses}".strip()
        parent_tokens = tokenize_text(parent_text)
        if len(parent_tokens) > PARENT_MAX_TOKENS:
            parent_text = detokenize_text(parent_tokens[:PARENT_MAX_TOKENS])

        if parent_text:
            chunks_list.append({
                "content": parent_text,
                "metadata": {
                    "parent_id": item_idx,
                    "chunk_id": chunk_id,
                    "title": title,
                    "query-text": query_text,
                    "citations": citations,
                    "url": url,
                    "is_parent": True,
                }
            })
            chunk_id += 1

        # Combine query + expert responses
        for resp_idx, resp in enumerate(responses, start=1):
            response = resp.get("response-text", "").strip()
            
            if not response:
                continue
                
            responder = resp.get("responder", "Expert")
            combined_text = f"Expert {responder}: {response}"
            
            # Chunk the response text
            text_chunks = chunk_text(combined_text)
            
            for chunk_text_content in text_chunks:
                chunks_list.append({
                    "content": chunk_text_content,
                    "metadata": {
                        "parent_id": item_idx,
                        "chunk_id": chunk_id,
                        "title": title,
                        "query-text": query_text,
                        "citations": citations,
                        "url": url,
                        "is_parent": False,
                    }
                })
                chunk_id += 1

    with open(output_file, "w", encoding="utf-8") as out:
        json.dump(chunks_list, out, indent=2, ensure_ascii=False)

    print(f"✅ Saved {len(chunks_list)} chunks → {output_file}")
    if overflow_count > 0:
        print(f"⚠️  Truncated {overflow_count} query texts to prevent overflow")

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
    print("📊 Chunk size optimized for InLegal-Sbert (768-dim) embeddings")
