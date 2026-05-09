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

# All persistent state lives under /app/db (DuckDB + raw match archive +
# strategy / notes / bios / vods / roster_history JSON). On Railway, mount
# a Volume at /app/db to survive redeploys.
#
# We still COPY db/ and data/ into the image so a fresh container has seed
# files: the lifespan migration in src/valorant_analyst/server/persist_migrate.py
# moves anything from data/ into db/ on first start, and is idempotent
# afterwards.
COPY db/ db/
COPY data/ data/

RUN mkdir -p \
    db/raw/matches \
    db/strategy \
    db/notes \
    db/bios

# Default env (override via Railway env vars or docker-compose)
ENV SERVER_HOST=0.0.0.0
ENV SERVER_PORT=8000
ENV SERVER_RELOAD=0

EXPOSE 8000

# Use Python so PORT is read from the real environment (Railway often injects
# a broken custom start command with a literal "$PORT" string).
CMD ["python", "-m", "valorant_analyst.serve_production"]
