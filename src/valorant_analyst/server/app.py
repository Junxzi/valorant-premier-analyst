"""FastAPI application factory + uvicorn entry point."""

from __future__ import annotations

import asyncio
import contextlib
import logging
import os
from collections.abc import AsyncIterator
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[3] / ".env", override=False)

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse

from .routes import health, matches, players, sync, teams, vods
from .scheduler import load_scheduler_config, periodic_sync_loop  # noqa: E402

logger = logging.getLogger("valorant_analyst.server")


def _allowed_origins() -> list[str]:
    raw = os.getenv(
        "CORS_ORIGINS",
        "http://localhost:3000,http://localhost:3001,http://localhost:3002,http://localhost:3003",
    )
    return [o.strip() for o in raw.split(",") if o.strip()]


@contextlib.asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Manage the background sync scheduler over the app's lifetime."""
    cfg = load_scheduler_config()
    task: asyncio.Task[None] | None = None
    if cfg.enabled:
        task = asyncio.create_task(
            periodic_sync_loop(cfg.interval_seconds, cfg.initial_delay_seconds),
            name="sync-scheduler",
        )
    else:
        logger.warning(
            "Auto-sync scheduler disabled (%s). Set SYNC_AUTO_ENABLED=1 and "
            "ensure HENRIK_API_KEY / PREMIER_TEAM_NAME / PREMIER_TEAM_TAG are "
            "configured to enable it.",
            cfg.disabled_reason,
        )

    try:
        yield
    finally:
        if task is not None:
            task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await task


def create_app() -> FastAPI:
    """Build the FastAPI app. Tests use this to inject overrides."""
    app = FastAPI(
        title="Valorant Premier Analyst",
        version="0.1.0",
        description=(
            "vlr.gg-style Premier team dashboard backend. All endpoints "
            "live under /api and read from a local DuckDB file."
        ),
        lifespan=lifespan,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=_allowed_origins(),
        allow_credentials=True,
        allow_methods=["GET", "PUT", "POST"],
        allow_headers=["*"],
    )
    app.include_router(health.router, prefix="/api")
    app.include_router(teams.router, prefix="/api")
    app.include_router(matches.router, prefix="/api")
    app.include_router(players.router, prefix="/api")
    app.include_router(sync.router, prefix="/api")
    app.include_router(vods.router, prefix="/api")

    @app.get("/", include_in_schema=False)
    async def redirect_root_docs() -> RedirectResponse:
        """Bare URL opens API docs instead of 404."""
        return RedirectResponse(url="/docs")

    return app


app = create_app()


def run() -> None:
    """Entry point exposed via the ``valorant-analyst-server`` script."""
    import uvicorn

    uvicorn.run(
        "valorant_analyst.server.app:app",
        host=os.getenv("SERVER_HOST", "127.0.0.1"),
        port=int(os.getenv("SERVER_PORT", "8000")),
        reload=os.getenv("SERVER_RELOAD", "1") == "1",
    )


if __name__ == "__main__":
    run()
