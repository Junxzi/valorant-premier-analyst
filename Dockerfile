# ── FastAPI backend ─────────────────────────────────────────────────────────
FROM python:3.11-slim

WORKDIR /app

# Install dependencies
COPY pyproject.toml .
COPY src/ src/

RUN pip install --no-cache-dir -e . && \
    mkdir -p db data/raw data/strategy data/bios

# Default env (override via Railway env vars or docker-compose)
ENV SERVER_HOST=0.0.0.0
ENV SERVER_PORT=8000
ENV SERVER_RELOAD=0

EXPOSE 8000

CMD ["uvicorn", "valorant_analyst.server.app:app", \
     "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
