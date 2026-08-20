# 🇮🇳 Quick Start: Indian Law Models Setup

This guide will help you quickly migrate to Indian law-specific models.

## ⚡ Quick Setup (5 minutes)

### Step 1: Update Environment Variables

Copy the updated template to your `.env` file:

```bash
cd backend
cp env.template .env
```

Then edit `.env` and add your API keys:

```bash
# Update these values
HUGGINGFACE_API_KEY=your_actual_huggingface_api_key_here
DATABASE_URL=your_actual_database_url_here
JWT_SECRET_KEY=your_actual_jwt_secret_here

# These are already set to Indian models:
LLM_MODEL=law-ai/InLegalLlama
EMBEDDING_MODEL=law-ai/InLegal-Sbert
EMBEDDING_DIMENSION=768
MILVUS_COLLECTION_NAME=indian_family_law_cases
```

### Step 2: Run Automated Setup

```bash
python setup_indian_law_db.py
```

This will:
- ✅ Process both JSON files from `data/family_law_domain/`
- ✅ Create optimized chunks (600 tokens, 80 overlap)
- ✅ Download InLegal-Sbert model (~440 MB on first run)
- ✅ Generate 768-dimensional embeddings
- ✅ Create new Milvus collection `indian_family_law_cases`
- ✅ Load all data into the database

**Expected time:** 10-15 minutes (depending on internet speed)

### Step 3: Verify Setup

The script will automatically verify:
- Chunk files created
- Embedding files with 768 dimensions
- Milvus collection populated

### Step 4: Start Your Application

```bash
# Start backend
python app.py  # or uvicorn app:app --reload

# In another terminal, start frontend
cd ../frontend
npm run dev
```

## 📊 What Changed?

### Models Upgraded

| Component | Old Model | New Model | Improvement |
|-----------|-----------|-----------|-------------|
| **LLM** | Llama 3.1 8B | InLegalLlama 7B | Indian legal training |
| **Embeddings** | all-MiniLM-L6-v2 | InLegal-Sbert | Legal text optimized |
| **Dimensions** | 384 | 768 | Better representation |

### Files Modified

✅ `config.py` - Updated default models  
✅ `embedding.py` - InLegal-Sbert integration  
✅ `chunking.py` - Optimized chunk sizes  
✅ `milvus_store.py` - 768-dimensional schema  
✅ `nodes/retriever.py` - Uses config settings  
✅ `nodes/generator.py` - Uses config settings  
✅ `nodes/query_analyzer.py` - Uses config settings  
✅ `nodes/information_gatherer.py` - Uses config settings  
✅ `nodes/reasoning_explainer.py` - Uses config settings  
✅ `nodes/update_handler.py` - Uses config settings  

## 🔍 Testing Your Setup

### Test 1: Check Collection

```python
from pymilvus import MilvusClient
import os
import dotenv

dotenv.load_dotenv()

client = MilvusClient(
    uri=os.getenv("MILVUS_URI"),
    token=os.getenv("MILVUS_TOKEN")
)

stats = client.get_collection_stats("indian_family_law_cases")
print(f"Total documents: {stats['row_count']}")
# Expected: 2000-4000 documents
```

### Test 2: Test Embedding

```python
from sentence_transformers import SentenceTransformer

model = SentenceTransformer("law-ai/InLegal-Sbert")
embedding = model.encode(["Section 498A of Indian Penal Code"])
print(f"Embedding dimension: {len(embedding[0])}")
# Expected: 768
```

### Test 3: Test Search

```python
from nodes.retriever import retrieve_documents
from state import FamilyLawState

state = FamilyLawState(
    query="What are the grounds for divorce under Hindu Marriage Act?"
)

result = retrieve_documents(state)
print(f"Retrieved: {len(result['retrieved_chunks'])} chunks")
print(f"Sources: {len(result['sources'])} sources")
# Expected: 5 chunks, multiple sources
```

## 🐛 Troubleshooting

### Issue: "Model not found"

**Solution:**
```bash
# Verify model name
pip install -U sentence-transformers
python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('law-ai/InLegal-Sbert')"
```

### Issue: "Dimension mismatch"

**Problem:** Old 384-dim embeddings still present  
**Solution:**
```bash
# Delete old embeddings
rm -rf data/embeddings/*
# Regenerate with new model
python embedding.py
```

### Issue: "Collection already exists"

**Solution:**
```bash
# Script will prompt you to drop it
# Or manually change collection name in .env:
MILVUS_COLLECTION_NAME=indian_law_v2
```

### Issue: "Chunk size overflow"

**Solution:** Already fixed! New chunking uses 600 tokens (down from 800)

### Issue: "API rate limit"

**Solution:** HuggingFace Inference API has rate limits. Consider:
- Using a paid HF account
- Running models locally (requires GPU)
- Adding delays between requests

## 🎯 Performance Expectations

### Embedding Generation
- **Speed:** ~50-100 chunks/second
- **Total time:** 5-10 minutes for both JSON files
- **Disk space:** ~100-200 MB

### Search Performance
- **Latency:** 50-200ms per query
- **Accuracy:** Improved for Indian legal queries
- **Recall:** Better citation matching

### LLM Response
- **Latency:** 3-8 seconds per response
- **Quality:** Better understanding of Indian law context
- **Citations:** More accurate IPC/CrPC/Act references

## 📚 Model Details

### InLegalLlama (7B)
- **Training:** Indian legal corpus (judgments, acts, precedents)
- **Context:** 4096 tokens
- **Languages:** English (legal), some Hindi
- **Strengths:** Indian legal reasoning, citation generation
- **License:** Check model card

### InLegal-Sbert (110M)
- **Training:** Legal document pairs
- **Output:** 768-dimensional dense vectors
- **Metric:** Cosine similarity
- **Strengths:** Legal terminology, semantic matching
- **License:** Check model card

### Alternative: IndianLegalGPT-8B

If InLegalLlama doesn't work well, try:

```bash
# In .env
LLM_MODEL=law-ai/IndianLegalGPT-8B
```

Then restart your application (no need to re-embed).

## 🔄 Rollback Instructions

To revert to old models:

1. Update `.env`:
```bash
LLM_MODEL=meta-llama/Llama-3.1-8B-Instruct
EMBEDDING_MODEL=sentence-transformers/all-MiniLM-L6-v2
EMBEDDING_DIMENSION=384
MILVUS_COLLECTION_NAME=family_law_cases
```

2. Restart application

Your old collection should still be available (if you didn't delete it).

## 🚀 Next Steps

1. **Test queries** with Indian law context:
   - "What are grounds for divorce under Hindu Marriage Act?"
   - "Explain Section 498A of IPC"
   - "What is the process for filing a DV case?"

2. **Monitor performance**:
   - Check response accuracy
   - Measure latency
   - Review citation quality

3. **Fine-tune** if needed:
   - Adjust retrieval top-k (default: 5)
   - Modify chunk size/overlap
   - Update system prompts for Indian context

## 📞 Support

- **Model issues:** Check HuggingFace model cards
- **Milvus issues:** Verify connection string
- **Data issues:** Check JSON file format
- **API issues:** Verify HuggingFace API key

## 🎉 Success Indicators

You'll know it's working when:

✅ Queries return Indian law-specific results  
✅ Citations reference IPC, CrPC, Indian Acts  
✅ Responses understand Indian legal context  
✅ Precedents are from Indian cases  
✅ Legal reasoning follows Indian jurisprudence  

---

**Setup Date:** June 9, 2026  
**Version:** 2.0 (Indian Law Models)  
**Estimated Setup Time:** 15 minutes  
