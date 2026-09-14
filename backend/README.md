# Family Law Assistant — Backend API

FastAPI + LangGraph backend for the Indian Family Law Assistant.  
Deployed on **Render** (free web service).

## AI Models

All inference is delegated to separate HuggingFace Spaces — no models are loaded locally:

| Model | Space | Purpose |
|-------|-------|---------|
| Llama 3.1 8B Instruct | HF Inference API | Legal response generation |
| IndicConformer 600M | `rverma0631/MultilingualASR` | Indic language ASR |
| Whisper small | `rverma0631/Whisper` | English ASR + language ID |
| IndicParler-TTS | `R910/IndicParler_TTS` | Multilingual TTS |

## API Docs

Visit `/api/docs` for the interactive Swagger UI once deployed.

## Environment Variables

Set these as **Render Environment Variables** (sensitive ones as Secret Files or env vars):

| Variable | Description |
|----------|-------------|
| `HUGGINGFACE_API_KEY` | HF token for inference and authenticated TTS/ASR Space calls |
| `DATABASE_URL` | Neon PostgreSQL asyncpg URL |
| `MILVUS_URI` | Zilliz Cloud endpoint |
| `MILVUS_TOKEN` | Zilliz Cloud API token |
| `JWT_SECRET_KEY` | JWT signing key |
| `CORS_ORIGINS` | `["https://your-app.vercel.app"]` |
| `WHISPER_SPACE_URL` | `rverma0631/Whisper` |
| `INDIC_ASR_SPACE_URL` | `rverma0631/MultilingualASR` |
| `INDIC_TTS_SPACE_URL` | `R910/IndicParler_TTS` |

## Local Development

```bash
cp env.template .env   # fill in your values
uv run uvicorn main:app --reload --port 8000
```

## ZeroGPU quota errors

Space clients use `HUGGINGFACE_API_KEY` from backend settings (Render environment
or local `.env`). Redeploy Render after changing the token or client code.
Authentication uses that HF account's quota; it does not remove ZeroGPU limits.
All users routed through this backend share that account's quota.

If HF reports `90s requested vs. 79s left`, the remaining quota cannot cover
the requested GPU allocation. Wait for the reset time reported by HF or use
a hosting/account option with sufficient capacity. Generated audio duration
is not GPU execution duration. Reducing a Space's `@spaces.GPU(duration=...)`
requires measuring its actual inference runtime, including long inputs.
