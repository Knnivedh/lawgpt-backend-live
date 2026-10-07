"""
Auto-indexing script for Kanoon Q&A data
"""
import json
import chromadb
from sentence_transformers import SentenceTransformer

print("=" * 80)
print("KANOON Q&A AUTO-INDEXING")
print("=" * 80)

# Load data
data_path = "C:/Users/Gourav Bhat/Downloads/LAW-GPT/DATA/kanoon.com/kanoon.com/kanoon_data.json"
print(f"\nLoading data from: {data_path}")

with open(data_path, 'r', encoding='utf-8') as f:
    data = json.load(f)

print(f"✓ Loaded {len(data)} Q&A entries")

# Group by query_url
print("\nGrouping responses by question...")
grouped = {}
for entry in data:
    url = entry['query_url']
    if url not in grouped:
        grouped[url] = {
            'title': entry['query_title'],
            'question': entry['query_text'],
            'category': entry.get('query_category', 'General'),
            'responses': []
        }
    if entry['response_text'].strip():
        grouped[url]['responses'].append(entry['response_text'])

print(f"✓ Grouped into {len(grouped)} unique questions")

# Create documents
print("\nPreparing documents...")
documents = []
for url, data_item in grouped.items():
    combined_responses = "\n\n---\n\n".join(data_item['responses'])
    doc_text = f"""QUESTION: {data_item['question']}

CATEGORY: {data_item['category']}

EXPERT RESPONSES:
{combined_responses}"""
    
    documents.append({
        'text': doc_text,
        'metadata': {
            'source': 'kanoon_qa',
            'category': data_item['category'],
            'title': data_item['title'],
            'url': url,
            'num_responses': len(data_item['responses'])
        }
    })

print(f"✓ Prepared {len(documents)} documents")

# Initialize ChromaDB (use parent directory to match RAG system)
print("\nInitializing ChromaDB...")
db_path = "C:/Users/Gourav Bhat/Downloads/LAW-GPT/chroma_db_hybrid"
print(f"Database path: {db_path}")
client = chromadb.PersistentClient(path=db_path)
collection = client.get_or_create_collection(
    name="legal_db_hybrid",
    metadata={"hnsw:space": "cosine"}
)

current_count = collection.count()
print(f"Current documents in database: {current_count}")

# Initialize embedding model
print("\nLoading embedding model...")
model = SentenceTransformer('sentence-transformers/all-MiniLM-L6-v2')
print("✓ Embedding model loaded")

# Index in batches
batch_size = 50
total_batches = (len(documents) + batch_size - 1) // batch_size

print(f"\nIndexing {len(documents)} documents in {total_batches} batches...")
print("This will take 5-10 minutes. Please wait...")

success_count = 0
for i in range(0, len(documents), batch_size):
    batch = documents[i:i + batch_size]
    batch_num = (i // batch_size) + 1
    
    print(f"Batch {batch_num}/{total_batches}...", end=" ", flush=True)
    
    texts = [doc['text'] for doc in batch]
    metadatas = [doc['metadata'] for doc in batch]
    ids = [f"kanoon_qa_{current_count + i + j}" for j in range(len(batch))]
    
    # Generate embeddings
    embeddings = model.encode(texts, show_progress_bar=False).tolist()
    
    try:
        collection.add(
            documents=texts,
            metadatas=metadatas,
            ids=ids,
            embeddings=embeddings
        )
        print("✓")
        success_count += len(batch)
    except Exception as e:
        print(f"✗ Error: {e}")
        continue

# Final count
final_count = collection.count()
print(f"\n{'='*80}")
print(f"✅ INDEXING COMPLETE!")
print(f"Total documents in database: {final_count}")
print(f"Successfully added: {success_count} documents")
print(f"\n🎯 RAG system will now retrieve documents for legal queries!")
print(f"🔄 Restart the backend server to see the changes")
print(f"{'='*80}")
