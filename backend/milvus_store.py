import os
import json
from pymilvus import MilvusClient, DataType
from tqdm import tqdm
import dotenv

dotenv.load_dotenv()

# ================= CONFIG =================
# New collection name for Indian Law embeddings
COLLECTION_NAME = os.getenv("MILVUS_COLLECTION_NAME", "indian_family_law_cases")
EMBEDDINGS_DIR = os.getenv("EMBEDDINGS_DIR", "./data/embeddings")
EMBEDDING_DIM = int(os.getenv("EMBEDDING_DIMENSION", 768))  # InLegal-Sbert uses 768 dimensions

milvus_uri = os.getenv("MILVUS_URI")
token = os.getenv("MILVUS_TOKEN")

print(f"📌 Collection: {COLLECTION_NAME}")
print(f"📏 Embedding Dimension: {EMBEDDING_DIM} (InLegal-Sbert)")

# ================= CONNECT =================
def connect_milvus():
    client = MilvusClient(uri=milvus_uri, token=token)
    print(f"✅ Connected to Milvus at {milvus_uri}")
    return client

# ================= CREATE COLLECTION =================
def create_collection(client, drop_if_exists=False):
    """
    Create a new collection for Indian Law embeddings.
    Set drop_if_exists=True to replace existing collection.
    """
    if client.has_collection(COLLECTION_NAME):
        if drop_if_exists:
            print(f"⚠️  Dropping existing collection '{COLLECTION_NAME}'...")
            client.drop_collection(COLLECTION_NAME)
        else:
            print(f"⚠️  Collection '{COLLECTION_NAME}' already exists!")
            response = input("Drop and recreate? (yes/no): ")
            if response.lower() == 'yes':
                client.drop_collection(COLLECTION_NAME)
            else:
                print("❌ Aborted. Keeping existing collection.")
                return False

    # Schema with 768-dimensional embeddings
    schema = client.create_schema()

    schema.add_field("id", DataType.INT64, is_primary=True, auto_id=True)
    schema.add_field("chunk_id", DataType.INT64)
    schema.add_field("content", DataType.VARCHAR, max_length=65535)
    schema.add_field("embedding", DataType.FLOAT_VECTOR, dim=EMBEDDING_DIM)
    schema.add_field("parent_id", DataType.INT64)
    schema.add_field("title", DataType.VARCHAR, max_length=1000)
    schema.add_field("query_text", DataType.VARCHAR, max_length=10000)
    schema.add_field("url", DataType.VARCHAR, max_length=1000)
    schema.add_field("category", DataType.VARCHAR, max_length=100)
    schema.add_field("citations", DataType.VARCHAR, max_length=5000)
    # Hierarchical RAG: True for the one full-item "parent" record per Q&A item,
    # False for the fine-grained child chunks. Lets retrieval search children for
    # precision, then expand matches back to their parent's full context.
    schema.add_field("is_parent", DataType.BOOL)

    # Index optimized for cosine similarity
    index_params = client.prepare_index_params()
    index_params.add_index(
        field_name="embedding",
        metric_type="COSINE",
        index_type="IVF_FLAT",
        params={"nlist": 128}
    )

    client.create_collection(
        COLLECTION_NAME,
        schema=schema,
        index_params=index_params
    )

    print(f"✅ Collection '{COLLECTION_NAME}' created with {EMBEDDING_DIM}-dimensional embeddings")
    return True

# ================= INSERT =================
def read_records(file_path):
    """Yield embedded records from a .jsonl (one per line) or legacy .json (array) file."""
    with open(file_path, "r", encoding="utf-8") as f:
        if file_path.endswith(".jsonl"):
            for line in f:
                if line.strip():
                    yield json.loads(line)
        else:
            yield from json.load(f)


def to_row(chunk, category, chunk_id):
    citations = chunk["metadata"].get("citations", [])
    citations_str = ", ".join(citations) if isinstance(citations, list) else str(citations)
    return {
        "chunk_id": chunk_id,
        "content": chunk["content"][:65535],
        "embedding": chunk["embedding"],
        "parent_id": chunk["metadata"]["parent_id"],
        "title": chunk["metadata"]["title"][:1000],
        "query_text": chunk["metadata"]["query-text"][:10000],
        "url": chunk["metadata"].get("url", "")[:1000],
        "category": category,
        "citations": citations_str[:5000],
        "is_parent": bool(chunk["metadata"].get("is_parent", False)),
    }


def insert_embeddings(client, batch_size=100):
    """Insert embeddings from every file in the embeddings directory, in batches."""
    embedding_files = sorted(
        f for f in os.listdir(EMBEDDINGS_DIR) if f.endswith(("_embeddings.json", "_embeddings.jsonl"))
    )

    if not embedding_files:
        print("❌ No embedding files found in", EMBEDDINGS_DIR)
        return 0

    total_inserted = 0
    failed = 0

    def flush(batch):
        nonlocal total_inserted, failed
        if not batch:
            return
        try:
            client.insert(COLLECTION_NAME, batch)
            total_inserted += len(batch)
        except Exception as e:
            failed += len(batch)
            print(f"❌ Error inserting a batch of {len(batch)}: {e}")

    next_chunk_id = 0  # unique across files (the per-file "id" restarts at 0)
    for filename in embedding_files:
        category = filename.replace("_embeddings.jsonl", "").replace("_embeddings.json", "")
        before = total_inserted
        batch = []
        for chunk in tqdm(read_records(os.path.join(EMBEDDINGS_DIR, filename)), desc=f"Inserting {category}"):
            if len(chunk["embedding"]) != EMBEDDING_DIM:
                print(f"⚠️  Skipping record {chunk.get('id')}: {len(chunk['embedding'])} dimensions")
                continue
            batch.append(to_row(chunk, category, next_chunk_id))
            next_chunk_id += 1
            if len(batch) >= batch_size:
                flush(batch)
                batch = []
        flush(batch)
        print(f"✅ Inserted {total_inserted - before} chunks from {category}")

    client.flush(COLLECTION_NAME)
    print(f"\n🎯 Total inserted: {total_inserted} chunks" + (f" ({failed} failed)" if failed else ""))
    return total_inserted

# ================= LOAD =================
def load_collection(client):
    """Load collection into memory for searching."""
    client.load_collection(COLLECTION_NAME)
    print(f"✅ Collection '{COLLECTION_NAME}' loaded into memory")

# ================= VERIFY =================
def verify_collection(client):
    """Verify the collection statistics."""
    stats = client.get_collection_stats(COLLECTION_NAME)
    print(f"\n📊 Collection Statistics:")
    print(f"   Collection: {COLLECTION_NAME}")
    print(f"   Row Count: {stats.get('row_count', 'N/A')}")
    print(f"   Embedding Dimension: {EMBEDDING_DIM}")

# ================= MAIN =================
if __name__ == "__main__":
    print("=" * 60)
    print("🇮🇳 Indian Family Law Vector Database Setup")
    print("=" * 60)
    
    client = connect_milvus()
    
    # Create new collection (will prompt if exists)
    if create_collection(client, drop_if_exists=False):
        # Insert embeddings
        count = insert_embeddings(client)
        
        if count > 0:
            # Load collection
            load_collection(client)
            
            # Verify
            verify_collection(client)
            
            print("\n✨ Milvus setup complete!")
            print(f"✅ {COLLECTION_NAME} is ready with {EMBEDDING_DIM}-dimensional InLegal-Sbert embeddings")
        else:
            print("\n❌ No embeddings were inserted. Please check your data.")
    else:
        print("\n❌ Collection creation cancelled or failed.")