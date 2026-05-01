"""Competitive intelligence API endpoints."""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import desc

from app.core.database import get_db
from app.models import CompetitorProfile
from app.services.competitive_intel_service import build_competitive_intel

router = APIRouter(prefix="/competitive-intel", tags=["competitive-intel"])


@router.get("/")
def get_competitive_intel(db: Session = Depends(get_db)):
    """Return competitive intelligence dashboard data.

    Includes: major project cards, head-to-head bid comparisons,
    live competitive tenders, and competitor activity summary.
    """
    return build_competitive_intel(db)


@router.get("/profiles")
def get_competitor_profiles(db: Session = Depends(get_db)):
    """Return AI-generated competitor behaviour profiles."""
    profiles = (
        db.query(CompetitorProfile)
        .order_by(desc(CompetitorProfile.overlap_with_scc))
        .all()
    )
    return {
        "profiles": [
            {
                "id": p.id,
                "competitor_name": p.competitor_name,
                "behaviour_summary": p.behaviour_summary,
                "threat_level": p.threat_level,
                "scc_strategy": p.scc_strategy,
                "conversion_rate": p.conversion_rate,
                "overlap_with_scc": p.overlap_with_scc,
                "top_categories": p.top_categories or [],
                "top_governorates": p.top_governorates or [],
                "built_at": p.built_at.isoformat() if p.built_at else None,
            }
            for p in profiles
        ]
    }


@router.post("/build-profiles")
def trigger_build_profiles(db: Session = Depends(get_db)):
    """Trigger AI competitor profile building."""
    from app.services.competitor_profile_service import build_competitor_profiles
    return build_competitor_profiles(db)
