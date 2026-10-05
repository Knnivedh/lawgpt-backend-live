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
| `TTS_FALLBACK_SPACE_URL` | `rverma0631/TTS_Sanskrit`; empty disables fallback |
| `ENABLE_QUERY_TRANSLATION` | `false` by default. Translates non-English queries to English before retrieval only (see `nodes/retriever.py`); the original query is untouched for analysis/generation |
| `TRANSLATION_MODEL` | `google/gemma-3-4b-it`, called via HF Inference Providers like the LLM |
| `ENABLE_HYBRID_SEARCH` | `true` by default. Merges a BM25 keyword ranking with vector search; runs in-process, no API calls |
| `ENABLE_CORPUS_CURATION` | `true` by default. Skips off-topic documents and returns one document per subject (`corpus_curation.py`) |
| `ENABLE_QUERY_REWRITE` | `false` by default. Rewrites each question into a short search query before retrieval (one extra model call per English question) |
| `CITATION_GUARD_MODE` | `mixed` by default. What happens to a citation not found in the retrieved context: `strict` removes the sentence, `mixed` removes for sections, wrong act+section pairs and case names but only flags bare act names, `flag` removes for sections only |
| `TRANSLATION_ENABLED_LANGUAGES` | Optional comma-separated ISO 639-1 allowlist. Empty = all non-English queries (langdetect mislabels code-mixed text, so an allowlist skips it) |

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


## TTS fallback and cold starts

TTS tries the primary Space first, then `rverma0631/TTS_Sanskrit` if client
initialization, prediction (including ZeroGPU quota exhaustion), or audio retrieval
fails. Both receive the same text and voice description at `/generate_finetuned`.
Each distinct Space is attempted once per request. If both fail, the request fails
with both errors. Downloads are cleaned up for each attempt. The fallback default
requires no `.env` change; redeploy the backend to activate it.

This does not remove queue time, CPU inference latency, or cold starts. The backend
waits for the primary call to return or raise before switching; there is no quota
reset cache or application-level prediction deadline. Verify fallback language and
voice quality for the languages your application offers.

Hugging Face documents that CPU Basic Spaces sleep after 48 hours of inactivity,
and custom sleep settings require paid hardware:
https://huggingface.co/docs/hub/spaces-gpus#set-a-custom-sleep-time

For predictable availability, upgrade the Spaces to hardware configured never to
sleep, or host the models on an always-running machine with adequate RAM/compute.
Always-on CPU hosting removes sleep latency but may still synthesize slowly.
For a free demo, visit the Spaces before a session to wake them and run a short
sample to load any lazily initialized models. In each Space, load models once per
process and reuse them. These reduce startup overhead but cannot guarantee uptime.
A backend health check alone does not warm the separate model Spaces. Scheduled
HTTP pings are not a documented guarantee that a model stays loaded.

### Scheduled wake-up requests

`.github/workflows/keepalive.yml` runs every 10 minutes and can also be run manually
from GitHub Actions → **Keep Services Alive** → **Run workflow**. It checks Render's
`/health` plus the Gradio `/config` endpoint for Whisper, IndicConformer,
IndicParler TTS, and the Sanskrit TTS fallback. Each service runs independently,
with bounded retries for cold starts; failed requests fail their job.

To activate, push the workflow to the repository's default branch and enable
GitHub Actions. Add the repository Actions secret `RENDER_BACKEND_URL` with the
backend base URL (without `/health`). Public Space checks require no token.
If you change model Spaces in backend settings, update the workflow URLs too.

These requests can wake sleeping apps but do not run inference, warm lazily loaded
models, or replenish ZeroGPU quota. Free hosting can still sleep or restart.
GitHub schedules can be delayed, and public-repository schedules are disabled after
60 days without repository activity. See the
[GitHub schedule documentation](https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows#schedule).
