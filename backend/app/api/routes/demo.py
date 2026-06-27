from fastapi import APIRouter, Depends

from backend.app.api.deps import get_db, get_gemini, get_recommendations, get_vector_search
from backend.app.seed import seed_demo_data

router = APIRouter(prefix="/demo", tags=["demo"])


@router.post("/seed")
async def seed_demo(db=Depends(get_db), gemini=Depends(get_gemini), vector_search=Depends(get_vector_search), recommendations=Depends(get_recommendations)):
    result = await seed_demo_data(db, gemini, vector_search, reset=True)
    await recommendations.refresh_for_student(result.get("student_id", "student-demo-maya"))
    return result


@router.get("/ids")
async def demo_ids():
    return {
        "student_id": "student-demo-maya",
        "tutor_id": "tutor-demo-elena",
        "booking_id": "booking-demo-derivatives",
        "session_id": "session-demo-derivatives",
        "student_email": "student@tutorloop.demo",
        "password": "password123",
    }
