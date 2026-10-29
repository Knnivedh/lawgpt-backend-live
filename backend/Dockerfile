# ── Stage 1: Install dependencies ────────────────────────────────────────────
FROM python:3.11-slim AS builder

RUN pip install --no-cache-dir uv

WORKDIR /app

COPY requirements.txt ./

RUN uv venv /app/.venv && \
    uv pip install --no-cache-dir --python /app/.venv/bin/python torch --index-url https://download.pytorch.org/whl/cpu && \
    uv pip install --no-cache-dir --python /app/.venv/bin/python -r requirements.txt

# ── Stage 2: Runtime image ────────────────────────────────────────────────────
FROM python:3.11-slim

WORKDIR /app

COPY --from=builder /app/.venv /app/.venv

COPY . .

EXPOSE 8000

ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

RUN mkdir -p logs data/chunked data/embeddings

CMD ["sh", "-c", "uvicorn main:app --host 0.0.0.0 --port ${PORT:-8000}"]
