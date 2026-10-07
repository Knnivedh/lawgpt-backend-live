"""
Index Kanoon.com Q&A data into ChromaDB for RAG retrieval
Processes 102,176 legal Q&A entries from kanoon_data.json
"""

import json
import sys
from pathlib import Path

# Add parent directory to path
sys.path.append(str(Path(__file__).parent))

from rag_system.core.hybrid_chroma_store import HybridChromaStore

def load_kanoon_data():
    """Load the kanoon Q&A dataset"""
    data_path = Path("C:/Users/Gourav Bhat/Downloads/LAW-GPT/DATA/kanoon.com/kanoon.com/kanoon_data.json")
    
    print(f"Loading data from: {data_path}")
    with open(data_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    print(f"Loaded {len(data)} Q&A entries")
    return data

def prepare_documents(kanoon_data):
    """
    Prepare documents for indexing
    Combine multiple responses for same question into one document
    """
    # Group by query_url to combine multiple responses
    grouped = {}
    
    for entry in kanoon_data:
        url = entry['query_url']
        
        if url not in grouped:
            grouped[url] = {
                'title': entry['query_title'],
                'question': entry['query_text'],
                'category': entry.get('query_category', 'General'),
                'responses': []
            }
        
        # Add this response
        if entry['response_text'].strip():
            grouped[url]['responses'].append(entry['response_text'])
    
    # Create documents
    documents = []
    for url, data in grouped.items():
        # Combine all responses
        combined_responses = "\n\n---\n\n".join(data['responses'])
        
        # Create document text
        doc_text = f"""QUESTION: {data['question']}

CATEGORY: {data['category']}

EXPERT RESPONSES:
{combined_responses}"""
        
        documents.append({
            'text': doc_text,
            'metadata': {
                'source': 'kanoon_qa',
                'category': data['category'],
                'title': data['title'],
                'url': url,
                'num_responses': len(data['responses'])
            }
        })
    
    print(f"Prepared {len(documents)} unique Q&A documents")
    return documents

def index_documents(documents, batch_size=100):
    """Index documents into ChromaDB"""
    print("Initializing ChromaDB...")
    store = HybridChromaStore()
    
    print(f"Indexing {len(documents)} documents in batches of {batch_size}...")
    
    total_batches = (len(documents) + batch_size - 1) // batch_size
    for batch_num, i in enumerate(range(0, len(documents), batch_size), 1):
        print(f"Processing batch {batch_num}/{total_batches}...")
        batch = documents[i:i + batch_size]
        
        texts = [doc['text'] for doc in batch]
        metadatas = [doc['metadata'] for doc in batch]
        ids = [f"kanoon_qa_{i + j}" for j in range(len(batch))]
        
        try:
            store.collection.add(
                documents=texts,
                metadatas=metadatas,
                ids=ids
            )
        except Exception as e:
            print(f"Error indexing batch {i}: {e}")
            continue
    
    print("✅ Indexing complete!")
    print(f"Total documents in collection: {store.collection.count()}")

def main():
    """Main indexing pipeline"""
    print("=" * 80)
    print("KANOON.COM Q&A INDEXING PIPELINE")
    print("=" * 80)
    
    # Load data
    kanoon_data = load_kanoon_data()
    
    # Prepare documents
    documents = prepare_documents(kanoon_data)
    
    # Show category breakdown
    categories = {}
    for doc in documents:
        cat = doc['metadata']['category']
        categories[cat] = categories.get(cat, 0) + 1
    
    print("\nCategory breakdown:")
    for cat, count in sorted(categories.items(), key=lambda x: x[1], reverse=True)[:15]:
        print(f"  {cat}: {count} documents")
    
    # Index
    print(f"\n{'='*80}")
    response = input(f"Proceed with indexing {len(documents)} documents? (yes/no): ")
    if response.lower() != 'yes':
        print("Indexing cancelled.")
        return
    
    index_documents(documents)
    
    print("\n✅ ALL DONE! Your RAG system now has access to 102,176 Kanoon Q&As")
    print("🎯 The system will now retrieve relevant answers for most legal queries!")

if __name__ == "__main__":
    main()
