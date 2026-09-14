# ── Stage 1: Install dependencies ────────────────────────────────────────────
FROM python:3.11-slim AS builder

# Install uv (fast Python package manager)
RUN pip install --no-cache-dir uv

WORKDIR /app

# Copy only dependency files first (better layer caching)
COPY pyproject.toml ./

# Install all deps into /app/.venv
RUN uv venv .venv && \
    uv pip install --no-cache-dir -e "."

# ── Stage 2: Runtime image ────────────────────────────────────────────────────
FROM python:3.11-slim

WORKDIR /app

# Copy installed venv from builder
COPY --from=builder /app/.venv /app/.venv

# Copy application source
COPY . .

# Render injects $PORT dynamically; expose the default as a hint only
EXPOSE 8000

# Make sure Python finds our venv
ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

# Create directories the backend expects at runtime
RUN mkdir -p logs data/chunked data/embeddings

# Use $PORT from Render (falls back to 8000 for local dev)
CMD ["sh", "-c", "uvicorn main:app --host 0.0.0.0 --port ${PORT:-8000}"]
