from fastapi import APIRouter, Depends

from backend.app.api.deps import get_recommendations
from backend.app.schemas.recommendations import RecommendationOut

router = APIRouter(prefix="/students", tags=["recommendations"])


@router.get("/{student_id}/recommendations", response_model=list[RecommendationOut])
async def get_recommendations_for_student(student_id: str, recommendations=Depends(get_recommendations)):
    return await recommendations.get_for_student(student_id)
