from datetime import timedelta

from fastapi import APIRouter, Depends, Query

from backend.app.api.deps import get_db, get_vector_search
from backend.app.db.mongo import utc_now
from backend.app.schemas.tutors import TutorOut

router = APIRouter(prefix="/tutors", tags=["tutors"])


async def _bootstrap_tutor_availability(db, tutor_id: str, days: int) -> list[dict]:
    now = utc_now()
    slots: list[dict] = []
    for day_offset in range(1, days + 1):
        base = (now + timedelta(days=day_offset)).replace(hour=0, minute=0, second=0, microsecond=0)
        # 3 available and 1 blocked slot per day.
        templates = [
            (10, 0, "available", "Core concept walkthrough"),
            (11, 0, "available", "Worked examples"),
            (13, 30, "blocked", "Tutor unavailable"),
            (15, 0, "available", "Practice and Q&A"),
        ]
        for hour, minute, status, topic in templates:
            starts_at = base.replace(hour=hour, minute=minute)
            ends_at = starts_at + timedelta(minutes=30)
            slot = {
                "tutor_id": tutor_id,
                "subject": "General",
                "topic": topic,
                "starts_at": starts_at,
                "ends_at": ends_at,
                "duration_minutes": 30,
                "status": status,
            }
            slot_id = await db.insert_one("tutor_availability", slot)
            slot["_id"] = slot_id
            slots.append(slot)
    return slots


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


@router.get("/{tutor_id}/availability/calendar")
async def get_tutor_availability_calendar(
    tutor_id: str,
    days: int = Query(default=7, ge=1, le=30),
    db=Depends(get_db),
):
    now = utc_now()
    end = now + timedelta(days=days)
    slots = await db.find_many(
        "tutor_availability",
        {
            "tutor_id": tutor_id,
            "starts_at": {"$gte": now, "$lte": end},
        },
        sort=[("starts_at", 1)],
        limit=200,
    )
    if not slots:
        slots = await _bootstrap_tutor_availability(db, tutor_id, days)
    return slots
