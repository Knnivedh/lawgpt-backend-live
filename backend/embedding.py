import os
import json
from tqdm import tqdm
from sentence_transformers import SentenceTransformer

# Directories
CHUNKED_DIR = "./data/chunked"
EMBEDDINGS_DIR = "./data/embeddings"
os.makedirs(EMBEDDINGS_DIR, exist_ok=True)

# Load Indian Law-specific embedding model
MODEL_NAME = "bhavyagiri/InLegal-Sbert"  # 768-dimensional embeddings
print(f"Loading Indian Law embedding model: {MODEL_NAME}")
print("Note: This model provides 768-dimensional embeddings optimized for Indian legal context")
model = SentenceTransformer(MODEL_NAME)

def generate_embeddings(file_path):
    """Generate embeddings for all chunks in a file using InLegal-Sbert."""
    category_name = os.path.basename(file_path).replace("_chunks.json", "")
    output_file = os.path.join(EMBEDDINGS_DIR, f"{category_name}_embeddings.json")
    
    with open(file_path, "r", encoding="utf-8") as f:
        chunks = json.load(f)
    
    parent_count = sum(1 for chunk in chunks if chunk["metadata"].get("is_parent"))
    print(f"\n📊 Processing {len(chunks)} records from {category_name} "
          f"({parent_count} parent, {len(chunks) - parent_count} child)")

    # Extract content for batch processing - combining query and answer for better context.
    # Parent records use the same "Query: ... Answer: ..." framing; the sentence
    # transformer truncates internally, which is fine since parent embeddings only
    # need to be good enough for coarse topic matching, not exact recall.
    contents = [f"Query: {chunk['metadata']['query-text']}\nAnswer: {chunk['content']}" for chunk in chunks]
    
    # Generate embeddings in batches - InLegal-Sbert optimized for legal text
    print("Generating 768-dimensional embeddings with InLegal-Sbert...")
    embeddings = model.encode(contents, show_progress_bar=True, batch_size=32)
    
    # Verify embedding dimensions
    if len(embeddings[0]) != 768:
        print(f"⚠️  Warning: Expected 768 dimensions, got {len(embeddings[0])}")
    else:
        print(f"✅ Confirmed: Embeddings are 768-dimensional")
    
    # Add embeddings to chunks
    embedded_chunks = []
    for i, chunk in enumerate(chunks):
        embedded_chunks.append({
            "id": i,
            "content": chunk["content"],
            "embedding": embeddings[i].tolist(),
            "metadata": chunk["metadata"]
        })
    
    # Save to file
    with open(output_file, "w", encoding="utf-8") as out:
        json.dump(embedded_chunks, out, indent=2, ensure_ascii=False)
    
    print(f"✅ Saved {len(embedded_chunks)} embeddings → {output_file}")

if __name__ == "__main__":
    chunk_files = [f for f in os.listdir(CHUNKED_DIR) if f.endswith("_chunks.json")]
    
    if not chunk_files:
        print("❌ No chunk files found. Run chunking.py first.")
        exit(1)
    
    for filename in chunk_files:
        generate_embeddings(os.path.join(CHUNKED_DIR, filename))
    
    print("\n🎯 All embeddings generated with InLegal-Sbert (768-dim) and saved under:", EMBEDDINGS_DIR)