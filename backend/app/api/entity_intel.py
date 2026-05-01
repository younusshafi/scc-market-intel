"""Entity intelligence API endpoints."""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import desc

from app.core.database import get_db
from app.models import EntityIntelligence

router = APIRouter(prefix="/entity-intel", tags=["entity-intel"])


@router.get("/")
def get_entity_intel(db: Session = Depends(get_db)):
    """Return AI-generated entity intelligence."""
    entities = (
        db.query(EntityIntelligence)
        .order_by(desc(EntityIntelligence.total_tenders))
        .all()
    )
    return {
        "entities": [
            {
                "id": e.id,
                "entity_name": e.entity_name,
                "total_tenders": e.total_tenders,
                "scc_relevant_count": e.scc_relevant_count,
                "avg_fee": e.avg_fee,
                "strategic_value": e.strategic_value,
                "insight": e.insight,
                "action": e.action,
                "competitors_present": e.competitors_present or [],
                "top_categories": e.top_categories or [],
                "built_at": e.built_at.isoformat() if e.built_at else None,
            }
            for e in entities
        ]
    }


@router.post("/build")
def trigger_build_entity_intel(db: Session = Depends(get_db)):
    """Trigger AI entity intelligence building."""
    from app.services.entity_intel_service import build_entity_intel
    return build_entity_intel(db)
