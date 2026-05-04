"""Competitive intelligence API endpoints."""

import json
import logging
from pathlib import Path

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from sqlalchemy import desc

from app.core.database import get_db
from app.models import CompetitorProfile
from app.services.competitive_intel_service import build_competitive_intel

logger = logging.getLogger(__name__)

_GALFAR_JSON = (
    Path(__file__).resolve().parent.parent.parent.parent
    / "scraped_data"
    / "galfar_financials.json"
)

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


@router.get("/galfar-financials")
def get_galfar_financials():
    """Return latest Galfar financial data from MSX scrape.

    Reads the JSON snapshot written by app.jobs.scrape_galfar. If the file
    doesn't exist yet, returns a 404-style dict so the frontend can show a
    meaningful fallback instead of crashing.
    """
    if not _GALFAR_JSON.exists():
        return JSONResponse(
            status_code=404,
            content={"error": "Galfar financials not yet scraped. Run: python -m app.jobs.scrape_galfar"},
        )
    try:
        with open(_GALFAR_JSON) as f:
            data = json.load(f)
        return data
    except Exception as exc:
        logger.error("Failed to read galfar_financials.json: %s", exc)
        return JSONResponse(
            status_code=500,
            content={"error": "Could not read Galfar financials file"},
        )


@router.post("/scrape-galfar")
def trigger_galfar_scrape():
    """Run the Galfar MSX scraper on demand and return the result."""
    from app.scrapers.galfar_msx_scraper import run_scraper, save_to_json
    try:
        data = run_scraper()
        save_to_json(data, _GALFAR_JSON)
        return {"status": "ok", "data": data}
    except Exception as exc:
        logger.error("Galfar scrape failed: %s", exc)
        return JSONResponse(
            status_code=500,
            content={"error": f"Scrape failed: {exc}"},
        )
