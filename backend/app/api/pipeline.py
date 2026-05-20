"""Pipeline status API endpoints."""

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import desc

from app.core.database import get_db
from app.models import TenderPipeline

router = APIRouter(prefix="/pipeline", tags=["pipeline"])

VALID_STATUSES = {"PURSUING", "WATCHING", "PASS"}


class PipelineEntry(BaseModel):
    tender_number: str
    tender_title: Optional[str] = None
    entity: Optional[str] = None
    status: str
    notes: Optional[str] = None
    closing_date: Optional[str] = None


def _serialize(entry: TenderPipeline) -> dict:
    return {
        "tender_number": entry.tender_number,
        "tender_title": entry.tender_title,
        "entity": entry.entity,
        "status": entry.status,
        "notes": entry.notes,
        "closing_date": entry.closing_date,
        "marked_at": entry.marked_at.isoformat() if entry.marked_at else None,
        "updated_at": entry.updated_at.isoformat() if entry.updated_at else None,
    }


@router.get("/")
def list_pipeline(db: Session = Depends(get_db)):
    """List all pipeline entries ordered by marked_at descending."""
    entries = db.query(TenderPipeline).order_by(desc(TenderPipeline.marked_at)).all()
    return [_serialize(e) for e in entries]


@router.post("/")
def set_pipeline_status(body: PipelineEntry, db: Session = Depends(get_db)):
    """Add or update a pipeline entry (upsert by tender_number)."""
    if body.status not in VALID_STATUSES:
        raise HTTPException(status_code=400, detail=f"Invalid status: {body.status}. Must be one of {VALID_STATUSES}")

    existing = db.query(TenderPipeline).filter_by(tender_number=body.tender_number).first()
    if existing:
        existing.status = body.status
        if body.tender_title is not None:
            existing.tender_title = body.tender_title
        if body.entity is not None:
            existing.entity = body.entity
        if body.notes is not None:
            existing.notes = body.notes
        if body.closing_date is not None:
            existing.closing_date = body.closing_date
        existing.updated_at = datetime.utcnow()
        db.commit()
        db.refresh(existing)
        return _serialize(existing)
    else:
        entry = TenderPipeline(
            tender_number=body.tender_number,
            tender_title=body.tender_title,
            entity=body.entity,
            status=body.status,
            notes=body.notes,
            closing_date=body.closing_date,
        )
        db.add(entry)
        db.commit()
        db.refresh(entry)
        return _serialize(entry)


@router.get("/status/{tender_number}")
def get_pipeline_status(tender_number: str, db: Session = Depends(get_db)):
    """Get status for a single tender. Returns {status: null} if not in pipeline."""
    entry = db.query(TenderPipeline).filter_by(tender_number=tender_number).first()
    if not entry:
        return {"tender_number": tender_number, "status": None}
    return {"tender_number": entry.tender_number, "status": entry.status}


@router.delete("/{tender_number}")
def delete_pipeline_entry(tender_number: str, db: Session = Depends(get_db)):
    """Remove a tender from the pipeline."""
    entry = db.query(TenderPipeline).filter_by(tender_number=tender_number).first()
    if not entry:
        raise HTTPException(status_code=404, detail=f"Tender {tender_number} not in pipeline")
    db.delete(entry)
    db.commit()
    return {"success": True, "tender_number": tender_number}
