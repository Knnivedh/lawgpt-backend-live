# Migration to Indian Law-Specific Models

This document describes the migration from generic models to Indian law-specific models for improved legal context understanding.

## 🔄 Model Changes

### Language Models (LLM)

**Previous:**
- Model: `meta-llama/Llama-3.1-8B-Instruct` (8B parameters)
- Context: General purpose

**New:**
- Model: `law-ai/InLegalLlama` (7B parameters)
- Alternative: `law-ai/IndianLegalGPT-8B` (8B parameters)
- Context: Specialized for Indian legal system

### Embedding Models

**Previous:**
- Model: `sentence-transformers/all-MiniLM-L6-v2`
- Dimensions: 384
- Context: General purpose text embeddings

**New:**
- Model: `law-ai/InLegal-Sbert` (110M parameters)
- Dimensions: 768
- Context: Optimized for Indian legal text

## 📊 Key Differences

### Embedding Dimension Change
The dimension change from 384 to 768 requires:
1. ✅ New Milvus collection (cannot reuse old collection)
2. ✅ Re-embedding all existing data
3. ✅ Updated chunking parameters to prevent overflow

### Benefits
- **Better Legal Context**: Models trained on Indian legal corpus
- **Improved Retrieval**: Embeddings optimized for legal terminology
- **Cultural Relevance**: Understanding of Indian legal system nuances
- **Citation Recognition**: Better handling of Indian legal citations

## 🚀 Migration Steps

### 1. Update Environment Variables

Update your `.env` file (or use the provided `env.template`):

```bash
# Indian Law Specific Models
LLM_MODEL=law-ai/InLegalLlama
EMBEDDING_MODEL=law-ai/InLegal-Sbert
EMBEDDING_DIMENSION=768

# New collection name (to avoid conflicts)
MILVUS_COLLECTION_NAME=indian_family_law_cases
```

### 2. Run the Automated Setup

The easiest way to migrate is using the automated setup script:

```bash
cd backend
python setup_indian_law_db.py
```

This script will:
1. Process both JSON files from `data/family_law_domain/`
2. Create optimized chunks (600 tokens, 80 overlap)
3. Generate 768-dimensional embeddings
4. Create new Milvus collection
5. Load all data

### 3. Manual Setup (Alternative)

If you prefer manual control:

```bash
# Step 1: Create chunks
python chunking.py

# Step 2: Generate embeddings (downloads model on first run)
python embedding.py

# Step 3: Setup Milvus database
python milvus_store.py
```

## 📝 Configuration Changes

### chunking.py
- **Chunk size**: Reduced from 800 to 600 tokens
- **Overlap**: Reduced from 100 to 80 tokens
- **Max query length**: Reduced from 9000 to 8000 chars
- **Reason**: Prevent overflow with larger embedding dimensions

### embedding.py
- **Model**: Changed to `law-ai/InLegal-Sbert`
- **Output dimension**: 768 (verified automatically)
- **Context format**: Improved `Query: ... Answer: ...` format

### milvus_store.py
- **Embedding dimension**: Updated to 768
- **New field**: Added `citations` field for better metadata
- **Collection name**: Configurable via environment variable
- **Safety**: Prompts before dropping existing collection

### config.py
- **Default LLM**: `law-ai/InLegalLlama`
- **Default embedding**: `law-ai/InLegal-Sbert`
- **Default dimension**: 768

## 🗃️ Data Processing

### Source Files
Both JSON files are processed:
- `family_law.json`
- `family_law_2.json`

Backup files (`.json.bak`) are automatically excluded.

### Chunk Structure
```json
{
  "content": "Expert response text...",
  "metadata": {
    "parent_id": 0,
    "chunk_id": 123,
    "title": "Query title",
    "query-text": "Original question",
    "citations": ["Section 498A IPC", "..."],
    "url": "https://..."
  }
}
```

### Embedding Structure
```json
{
  "id": 123,
  "content": "Text content",
  "embedding": [768 float values],
  "metadata": { ... }
}
```

## 🔍 Verification

After setup, verify your data:

```python
from pymilvus import MilvusClient
import os
import dotenv

dotenv.load_dotenv()

client = MilvusClient(
    uri=os.getenv("MILVUS_URI"),
    token=os.getenv("MILVUS_TOKEN")
)

# Check collection
collection_name = os.getenv("MILVUS_COLLECTION_NAME")
stats = client.get_collection_stats(collection_name)
print(f"Total documents: {stats['row_count']}")

# Test search
results = client.search(
    collection_name=collection_name,
    data=[[0.1] * 768],  # dummy vector
    limit=5,
    output_fields=["content", "title"]
)
print(f"Search working: {len(results[0])} results")
```

## 🎯 Expected Results

### Chunk Counts
- Expect ~2000-3000 chunks per JSON file
- Exact count depends on response lengths

### Embedding Files
- Each file ~50-100 MB (depending on data)
- 768 dimensions per embedding
- JSON format for inspection

### Milvus Collection
- Collection name: `indian_family_law_cases` (or custom)
- Schema: 10 fields (id, chunk_id, content, embedding, etc.)
- Index: COSINE similarity with IVF_FLAT

## ⚠️ Important Notes

### Model Download
First run of `embedding.py` will download InLegal-Sbert (~440 MB):
```
Downloading model: law-ai/InLegal-Sbert
This may take a few minutes on first run...
```

### Old Collection
The old collection (`family_law_cases`) with 384-dim embeddings is **not automatically deleted**. You can:
- Keep it as backup
- Delete manually if needed
- It won't interfere with the new collection

### Memory Requirements
- InLegal-Sbert: ~500 MB RAM
- Processing: ~1-2 GB RAM for embeddings
- Chunking: Minimal memory

## 🐛 Troubleshooting

### "Embedding dimension mismatch"
**Problem**: Old embeddings have 384 dimensions
**Solution**: Delete `data/embeddings/` and run `embedding.py` again

### "Collection already exists"
**Problem**: Collection name conflict
**Solution**: Script will prompt to drop and recreate, or change collection name in `.env`

### "Model not found"
**Problem**: InLegal-Sbert not available on HuggingFace
**Solution**: Verify model name is correct: `law-ai/InLegal-Sbert`

### "Chunk size overflow"
**Problem**: Chunks too large for Milvus VARCHAR fields
**Solution**: Already handled with reduced chunk size (600 tokens)

## 📚 Model References

### InLegalLlama
- Repository: `law-ai/InLegalLlama`
- Parameters: 7B
- Training: Indian legal corpus
- Context length: 4096 tokens

### InLegal-Sbert
- Repository: `law-ai/InLegal-Sbert`
- Parameters: 110M
- Output: 768-dimensional vectors
- Training: Indian legal documents

### Alternative: IndianLegalGPT
If InLegalLlama doesn't work, try:
```bash
LLM_MODEL=law-ai/IndianLegalGPT-8B
```

## 📖 Usage After Migration

Your application will now:
1. Use InLegalLlama for generating responses
2. Use InLegal-Sbert for embedding queries
3. Search in the new 768-dimensional vector space
4. Retrieve Indian law-specific context

No code changes needed in `graph.py`, `nodes/`, or `app.py` - they automatically use the configured models.

## 🔄 Rollback Instructions

If you need to revert to old models:

1. Update `.env`:
```bash
LLM_MODEL=meta-llama/Llama-3.1-8B-Instruct
EMBEDDING_MODEL=sentence-transformers/all-MiniLM-L6-v2
EMBEDDING_DIMENSION=384
MILVUS_COLLECTION_NAME=family_law_cases
```

2. Your old collection should still be available (if not deleted)

3. Restart the application

## 📞 Support

For issues with:
- **Models**: Check HuggingFace model cards
- **Milvus**: Verify connection string and token
- **Chunking**: Review `data/family_law_domain/*.json` format
- **Embeddings**: Check model download and disk space

---

**Migration Date**: June 9, 2026
**Version**: 2.0 (Indian Law Models)
