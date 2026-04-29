"""Competitive intelligence API endpoints."""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.services.competitive_intel_service import build_competitive_intel

router = APIRouter(prefix="/competitive-intel", tags=["competitive-intel"])


@router.get("/")
def get_competitive_intel(db: Session = Depends(get_db)):
    """Return competitive intelligence dashboard data.

    Includes: major project cards, head-to-head bid comparisons,
    live competitive tenders, and competitor activity summary.
    """
    return build_competitive_intel(db)
