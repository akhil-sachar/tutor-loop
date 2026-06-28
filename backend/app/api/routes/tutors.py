from fastapi import APIRouter, Depends, Query

from backend.app.api.deps import get_db, get_vector_search
from backend.app.schemas.tutors import TutorOut

router = APIRouter(prefix="/tutors", tags=["tutors"])


@router.get("/search", response_model=list[TutorOut])
async def search_tutors(
    q: str = Query(default=""),
    subject: str | None = None,
    max_rate: float | None = None,
    min_rating: float | None = None,
    limit: int = Query(default=8, ge=1, le=50),
    vector_search=Depends(get_vector_search),
):
    return await vector_search.search(
        query=q or subject or "experienced tutor",
        collections=["tutors"],
        filters={"subject": subject, "max_rate": max_rate, "min_rating": min_rating},
        limit=limit,
    )


@router.get("/{tutor_id}/availability")
async def get_tutor_availability(
    tutor_id: str,
    limit: int = Query(default=10, ge=1, le=50),
    db=Depends(get_db),
):
    return await db.find_many(
        "tutor_availability",
        {"tutor_id": tutor_id, "status": "available"},
        sort=[("starts_at", 1)],
        limit=limit,
    )
