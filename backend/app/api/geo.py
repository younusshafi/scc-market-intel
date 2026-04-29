"""Geographic distribution API endpoint."""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.services.geo_service import get_geographic_distribution

router = APIRouter(prefix="/geo", tags=["geography"])


@router.get("/distribution")
def geographic_distribution(db: Session = Depends(get_db)):
    """Return inferred geographic distribution of tenders across Oman's governorates."""
    return get_geographic_distribution(db)
