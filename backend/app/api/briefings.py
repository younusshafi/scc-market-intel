"""Briefing API endpoints."""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import desc

from app.core.database import get_db
from app.models import Briefing
from app.services.briefing_service import generate_and_store_briefing

router = APIRouter(prefix="/briefings", tags=["briefings"])


@router.get("/latest")
def get_latest_briefing(db: Session = Depends(get_db)):
    """Get the most recent executive briefing."""
    briefing = (
        db.query(Briefing)
        .order_by(desc(Briefing.generated_at))
        .first()
    )

    if not briefing:
        return {"briefing": None}

    return {
        "briefing": {
            "id": briefing.id,
            "content_md": briefing.content_md,
            "content_html": briefing.content_html,
            "generated_at": briefing.generated_at.isoformat(),
            "model_used": briefing.model_used,
        }
    }


@router.post("/generate")
def trigger_briefing(db: Session = Depends(get_db)):
    """Trigger generation of a new executive briefing."""
    briefing = generate_and_store_briefing(db)
    if not briefing:
        return {"status": "failed", "message": "LLM call returned no result"}
    return {
        "status": "success",
        "briefing_id": briefing.id,
        "generated_at": briefing.generated_at.isoformat(),
    }


@router.get("/history")
def list_briefings(db: Session = Depends(get_db)):
    """List all past briefings."""
    briefings = (
        db.query(Briefing)
        .order_by(desc(Briefing.generated_at))
        .limit(12)
        .all()
    )

    return [
        {
            "id": b.id,
            "generated_at": b.generated_at.isoformat(),
            "model_used": b.model_used,
            "preview": (b.content_md or "")[:200],
        }
        for b in briefings
    ]
