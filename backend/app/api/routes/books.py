from fastapi import APIRouter, Depends, HTTPException, Query

from backend.app.api.deps import get_db, get_vector_search
from backend.app.db.mongo import utc_now
from backend.app.schemas.books import BookAccessRequest, BookOut

router = APIRouter(prefix="/books", tags=["books"])


@router.get("/search", response_model=list[BookOut])
async def search_books(
    q: str = Query(..., min_length=2),
    subject: str | None = None,
    limit: int = Query(default=10, ge=1, le=50),
    db=Depends(get_db),
    vector_search=Depends(get_vector_search),
):
    filters = {"subject": subject} if subject else {}
    results = await vector_search.search(
        query=q,
        collections=["books", "book_chunks"],
        filters=filters,
        limit=limit,
    )
    seen: set[str] = set()
    books: list[dict] = []
    for item in results:
        book_id = item.get("book_id") or item.get("_id")
        if book_id in seen:
            continue
        seen.add(book_id)
        if item.get("content_type") == "book_chunk":
            book_doc = await db.find_one("books", {"_id": book_id}) if book_id else None
            books.append(
                {
                    "id": book_id,
                    "title": (book_doc or item).get("title", "Book"),
                    "subject": (book_doc or item).get("subject", ""),
                    "description": (book_doc or item).get("description", item.get("snippet", item.get("content", ""))[:260]),
                    "price": float((book_doc or item).get("price", 0)),
                    "rating": float((book_doc or item).get("rating", 4.5)),
                    "author": (book_doc or item).get("author"),
                }
            )
        else:
            books.append(
                {
                    "id": book_id,
                    "title": item.get("title", ""),
                    "subject": item.get("subject", ""),
                    "description": item.get("description", item.get("snippet", "")),
                    "price": float(item.get("price", 0)),
                    "rating": float(item.get("rating", 0)),
                    "author": item.get("author"),
                }
            )
    return books


@router.get("", response_model=list[BookOut])
async def list_books(db=Depends(get_db)):
    docs = await db.find_many("books", {}, limit=50)
    return [
        {
            "id": doc["_id"],
            "title": doc["title"],
            "subject": doc["subject"],
            "description": doc["description"],
            "price": float(doc.get("price", 0)),
            "rating": float(doc.get("rating", 0)),
            "author": doc.get("author"),
        }
        for doc in docs
    ]


@router.post("/{book_id}/access")
async def access_book(book_id: str, payload: BookAccessRequest, db=Depends(get_db)):
    book = await db.find_one("books", {"_id": book_id})
    if not book:
        raise HTTPException(status_code=404, detail="Book not found")
    await db.update_one(
        "student_learning_profiles",
        {"student_id": payload.student_id},
        {
            "$addToSet": {"purchased_book_ids": book_id},
            "$set": {"updated_at": utc_now()},
        },
        upsert=True,
    )
    return {
        "message": f"Added '{book['title']}' to your library. The AI tutor can now cite this book.",
        "book_id": book_id,
    }
