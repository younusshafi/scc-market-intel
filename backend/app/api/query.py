"""Natural language query endpoint."""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.services.query_service import process_query

router = APIRouter(prefix="/query", tags=["query"])


@router.get("/")
def query_intel(
    q: str = Query(..., description="Natural language query"),
    db: Session = Depends(get_db),
):
    """Process a bounded natural language query against the intelligence database.

    Supported patterns:
    - "How many tenders?" / "How many SCC tenders?"
    - "Show SCC opportunities" / "List re-tenders"
    - "Tenders closing this week"
    - "Tenders from Ministry of Transport"
    - "Show sub-contract tenders"
    - "News about Galfar" / "Competitor news"
    - "Market breakdown" / "Top entities"
    - "Pipeline summary" / "Dashboard status"
    - "When was data last updated?"
    """
    return process_query(db, q)
