"""Natural-Language Query (NLQ) API endpoint."""

from fastapi import APIRouter
from pydantic import BaseModel, Field

from app.services.nlq_service import ask

router = APIRouter(prefix="/nlq", tags=["nlq"])


class NLQRequest(BaseModel):
    question: str = Field(..., min_length=3, max_length=1000)


class NLQResponse(BaseModel):
    answer: str
    sql: str
    rows: list[dict]
    tier: int
    caveats: list[str] = []
    error: str | None = None


@router.post("/ask", response_model=NLQResponse)
def nlq_ask(req: NLQRequest):
    """Ask a natural-language question about SCC market intelligence data."""
    return ask(req.question)
