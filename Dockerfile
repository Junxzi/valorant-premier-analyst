# ── FastAPI backend ─────────────────────────────────────────────────────────
FROM python:3.11-slim

WORKDIR /app

# System packages needed by pandas / duckdb
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    g++ \
    && rm -rf /var/lib/apt/lists/*

# Install Python package
COPY pyproject.toml README.md ./
COPY src/ src/

RUN pip install --no-cache-dir -e .

# Copy initial data (DB + strategy/bios).
# These are overridden at runtime by the mounted Volume on Railway.
COPY db/ db/
COPY data/ data/

RUN mkdir -p db data/raw data/strategy data/bios

# Default env (override via Railway env vars or docker-compose)
ENV SERVER_HOST=0.0.0.0
ENV SERVER_PORT=8000
ENV SERVER_RELOAD=0

EXPOSE 8000

CMD ["uvicorn", "valorant_analyst.server.app:app", \
     "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
