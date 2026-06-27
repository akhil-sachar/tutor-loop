from fastapi import APIRouter, Depends, Query

from backend.app.api.deps import get_vector_search
from backend.app.schemas.search import SemanticSearchResult

router = APIRouter(prefix="/search", tags=["semantic-search"])


@router.get("", response_model=list[SemanticSearchResult])
async def semantic_search(
    q: str = Query(..., min_length=2),
    subject: str | None = None,
    content_type: str | None = None,
    max_price: float | None = None,
    max_rate: float | None = None,
    min_rating: float | None = None,
    limit: int = Query(default=10, ge=1, le=50),
    vector_search=Depends(get_vector_search),
):
    return await vector_search.search(
        query=q,
        collections=["notes", "tutors", "ai_reflections", "transcripts"],
        filters={
            "subject": subject,
            "content_type": content_type,
            "max_price": max_price,
            "max_rate": max_rate,
            "min_rating": min_rating,
        },
        limit=limit,
    )
