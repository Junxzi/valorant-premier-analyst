"""Docker / Railway entrypoint — reads PORT from the environment without shell."""

from __future__ import annotations

import os

import uvicorn


def main() -> None:
    port = int(os.environ.get("PORT", os.environ.get("SERVER_PORT", "8000")))
    host = os.environ.get("SERVER_HOST", "0.0.0.0")
    workers = int(os.environ.get("UVICORN_WORKERS", "1"))
    uvicorn.run(
        "valorant_analyst.server.app:app",
        host=host,
        port=port,
        workers=workers,
        reload=False,
    )


if __name__ == "__main__":
    main()
