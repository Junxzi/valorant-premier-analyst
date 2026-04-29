"""Health endpoint."""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends

from ..deps import db_path
from ..schemas import HealthResponse

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse)
def get_health(path: Path = Depends(db_path)) -> HealthResponse:
    return HealthResponse(
        status="ok",
        db_present=path.exists(),
        db_path=str(path),
    )
