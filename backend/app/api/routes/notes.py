from fastapi import APIRouter, Depends, HTTPException, Query

from backend.app.api.deps import get_db, get_recommendations, get_vector_search
from backend.app.schemas.notes import NoteCreate, NoteOut, PurchaseOut, PurchaseRequest

router = APIRouter(prefix="/notes", tags=["notes"])


@router.get("/search", response_model=list[NoteOut])
async def search_notes(
    q: str = Query(default=""),
    subject: str | None = None,
    max_price: float | None = None,
    min_rating: float | None = None,
    limit: int = Query(default=8, ge=1, le=50),
    vector_search=Depends(get_vector_search),
):
    results = await vector_search.search(
        query=q or subject or "popular tutoring notes",
        collections=["notes"],
        filters={"subject": subject, "max_price": max_price, "min_rating": min_rating},
        limit=limit,
    )
    return results


@router.post("", response_model=NoteOut)
async def create_note(payload: NoteCreate, db=Depends(get_db), vector_search=Depends(get_vector_search)):
    note = payload.model_dump()
    note.update({"rating": 0, "purchases_count": 0, "content_type": "note"})
    note["embedding"] = await vector_search.embed_document(note, ["title", "subject", "description", "content"])
    note_id = await db.insert_one("notes", note)
    note["_id"] = note_id
    return note


@router.post("/{note_id}/purchase", response_model=PurchaseOut)
async def purchase_note(
    note_id: str,
    payload: PurchaseRequest,
    db=Depends(get_db),
    recommendations=Depends(get_recommendations),
):
    note = await db.find_one("notes", {"_id": note_id})
    if not note:
        raise HTTPException(status_code=404, detail="Note not found")

    purchase = {
        "note_id": note_id,
        "student_id": payload.student_id,
        "amount": note["price"],
        "status": "simulated_paid",
    }
    purchase_id = await db.insert_one("purchases", purchase)
    await db.update_one("notes", {"_id": note_id}, {"$inc": {"purchases_count": 1}})
    await db.update_one(
        "student_learning_profiles",
        {"student_id": payload.student_id},
        {"$addToSet": {"purchased_note_ids": note_id}},
        upsert=True,
    )
    await recommendations.refresh_for_student(payload.student_id)
    return {
        "purchase_id": purchase_id,
        "note_id": note_id,
        "student_id": payload.student_id,
        "status": "simulated_paid",
        "message": "Payment is mocked for the hackathon demo; purchase recorded.",
    }
