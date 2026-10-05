"""
embedding.py - embed every record produced by chunking.py.

Each record is embedded as "<title>\\n<text>". The title is capped at
TITLE_MAX_TOKENS so title + chunk always fits the model's 512-token input
(chunking.py sizes chunks to leave that room). Queries are embedded as plain
text at search time, with no extra framing on either side.

Two backends, which produce identical vectors:
  EMBED_BACKEND=api    (default) Hugging Face Inference API, in small batches
  EMBED_BACKEND=local  sentence-transformers on this machine; no API calls.
                       Not a project dependency, so run it as:
                       EMBED_BACKEND=local uv run --no-project --with sentence-transformers \\
                           --with tqdm --with tokenizers python embedding.py

Output is JSON Lines (one record per line), written as it goes, so neither
this script nor milvus_store.py has to hold every vector in memory. Records
are embedded in small slices with a small batch size: an earlier version sent
batches of 64 full-length texts and used 6.7 GB on an 8 GB machine.

Paths can be overridden with CHUNKED_DIR and EMBEDDINGS_DIR.
"""
import json
import os

from tokenizers import Tokenizer
from tqdm import tqdm

CHUNKED_DIR = os.getenv("CHUNKED_DIR", "./data/chunked")
EMBEDDINGS_DIR = os.getenv("EMBEDDINGS_DIR", "./data/embeddings")
os.makedirs(EMBEDDINGS_DIR, exist_ok=True)

MODEL_NAME = os.getenv("EMBEDDING_MODEL", "bhavyagiri/InLegal-Sbert")  # 768-dimensional
EMBEDDING_DIM = int(os.getenv("EMBEDDING_DIMENSION", "768"))  # 384 for BAAI/bge-small-en-v1.5
TITLE_MAX_TOKENS = 40
BACKEND = os.getenv("EMBED_BACKEND", "api")
API_BATCH_SIZE = 32
LOCAL_BATCH_SIZE = int(os.getenv("EMBED_BATCH_SIZE", "8"))
SLICE_SIZE = 256  # records embedded and written per step
# The model reads 512 tokens; text beyond this many characters can never be
# among them, so drop it before tokenizing (parents can be 60,000 characters).
MAX_EMBED_CHARS = 6000

_tokenizer = Tokenizer.from_pretrained(MODEL_NAME)
_tokenizer.no_truncation()


def embedding_text(title, content):
    """The exact text that is embedded for a record."""
    title = (title or "").strip()
    if title:
        encoding = _tokenizer.encode(title, add_special_tokens=False)
        if len(encoding.ids) > TITLE_MAX_TOKENS:
            title = title[:encoding.offsets[TITLE_MAX_TOKENS - 1][1]]
        content = f"{title}\n{content}"
    return content[:MAX_EMBED_CHARS]


def make_embedder():
    if BACKEND == "local":
        import torch
        from sentence_transformers import SentenceTransformer
        model = SentenceTransformer(MODEL_NAME)
        print(f"Embedding locally with {MODEL_NAME} on {model.device}, batch size {LOCAL_BATCH_SIZE}")

        def embed(texts):
            vectors = model.encode(texts, batch_size=LOCAL_BATCH_SIZE, show_progress_bar=False).tolist()
            if torch.backends.mps.is_available():
                torch.mps.empty_cache()  # release the GPU allocator's cache between slices
            return vectors
        return embed

    from embedding_client import HuggingFaceEmbeddingClient
    client = HuggingFaceEmbeddingClient(MODEL_NAME, EMBEDDING_DIM)
    print(f"Embedding with the Hugging Face Inference API ({MODEL_NAME})")

    def embed(texts):
        vectors = []
        for start in range(0, len(texts), API_BATCH_SIZE):
            vectors.extend(client.embed(texts[start:start + API_BATCH_SIZE]))
        return vectors
    return embed


def generate_embeddings(file_path, embed):
    category_name = os.path.basename(file_path).replace("_chunks.json", "")
    output_file = os.path.join(EMBEDDINGS_DIR, f"{category_name}_embeddings.jsonl")

    with open(file_path, "r", encoding="utf-8") as f:
        chunks = json.load(f)

    parent_count = sum(1 for chunk in chunks if chunk["metadata"].get("is_parent"))
    print(f"\n📊 Processing {len(chunks)} records from {category_name} "
          f"({parent_count} parent, {len(chunks) - parent_count} child)", flush=True)

    # Parents are embedded too (the schema needs a vector) but are never
    # searched; only their first 512 tokens count, which is fine.
    written = 0
    with open(output_file, "w", encoding="utf-8") as out:
        for start in tqdm(range(0, len(chunks), SLICE_SIZE), desc=f"Embedding {category_name}"):
            batch = chunks[start:start + SLICE_SIZE]
            vectors = embed([embedding_text(c["metadata"]["title"], c["content"]) for c in batch])
            if len(vectors) != len(batch) or len(vectors[0]) != EMBEDDING_DIM:
                raise RuntimeError(f"Unexpected embedding output at record {start}")
            for offset, (chunk, vector) in enumerate(zip(batch, vectors)):
                record = {"id": start + offset, "content": chunk["content"],
                          "embedding": vector, "metadata": chunk["metadata"]}
                out.write(json.dumps(record, ensure_ascii=False) + "\n")
                written += 1

    print(f"✅ Saved {written} embeddings → {output_file}", flush=True)


if __name__ == "__main__":
    chunk_files = sorted(f for f in os.listdir(CHUNKED_DIR) if f.endswith("_chunks.json"))

    if not chunk_files:
        print("❌ No chunk files found. Run chunking.py first.")
        exit(1)

    embedder = make_embedder()
    for filename in chunk_files:
        generate_embeddings(os.path.join(CHUNKED_DIR, filename), embedder)

    print("\n🎯 All embeddings generated and saved under:", EMBEDDINGS_DIR)
