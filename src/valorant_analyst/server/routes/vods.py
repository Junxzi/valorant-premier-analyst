"""GET/PUT for ``data/vods.json`` — same trust model as team strategy edits."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from ..vods import load_vods, save_vods

router = APIRouter(prefix="/vods", tags=["vods"])


class VodsEnvelope(BaseModel):
    urls: dict[str, str] = Field(description="match_id → VOD URL (http/https only).")


@router.get("", response_model=VodsEnvelope)
def get_vods() -> VodsEnvelope:
    return VodsEnvelope(urls=load_vods())


@router.put("", response_model=VodsEnvelope)
def put_vods(body: VodsEnvelope) -> VodsEnvelope:
    try:
        urls = save_vods(body.urls)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except OSError as e:
        raise HTTPException(
            status_code=500,
            detail=f"Could not write vods file: {e}",
        ) from e
    return VodsEnvelope(urls=urls)
