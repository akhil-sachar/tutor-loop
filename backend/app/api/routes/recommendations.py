from fastapi import APIRouter, Depends

from backend.app.api.deps import get_db, get_recommendations
from backend.app.schemas.library import StudentLibraryOut
from backend.app.schemas.recommendations import RecommendationOut

router = APIRouter(prefix="/students", tags=["recommendations"])


@router.get("/{student_id}/recommendations", response_model=list[RecommendationOut])
async def get_recommendations_for_student(student_id: str, recommendations=Depends(get_recommendations)):
    return await recommendations.get_for_student(student_id)


@router.get("/{student_id}/library", response_model=StudentLibraryOut)
async def get_student_library(student_id: str, db=Depends(get_db)):
    profile = await db.find_one("student_learning_profiles", {"student_id": student_id}) or {}

    note_ids = profile.get("purchased_note_ids", []) or []
    book_ids = profile.get("purchased_book_ids", []) or []

    notes = []
    for note_id in note_ids:
        note = await db.find_one("notes", {"_id": note_id})
        if not note:
            continue
        notes.append(
            {
                "id": note_id,
                "title": note.get("title", "Untitled note"),
                "subject": note.get("subject"),
                "description": note.get("description", ""),
                "content": note.get("content", ""),
                "price": float(note.get("price", 0)),
            }
        )

    books = []
    for book_id in book_ids:
        book = await db.find_one("books", {"_id": book_id})
        if not book:
            continue
        chunks = await db.find_many("book_chunks", {"book_id": book_id}, sort=[("chunk_index", 1)], limit=1)
        preview = chunks[0].get("content", "")[:500] if chunks else ""
        books.append(
            {
                "id": book_id,
                "title": book.get("title", "Untitled book"),
                "subject": book.get("subject"),
                "description": book.get("description", ""),
                "author": book.get("author"),
                "preview": preview,
            }
        )

    return {"student_id": student_id, "notes": notes, "books": books}
