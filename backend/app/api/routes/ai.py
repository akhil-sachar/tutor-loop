from fastapi import APIRouter, Depends

from backend.app.api.deps import get_db, get_gemini, get_vector_search
from backend.app.schemas.ai import AIChatRequest, AIChatResponse

router = APIRouter(prefix="/ai", tags=["ai"])


@router.post("/chat", response_model=AIChatResponse)
async def ai_chat(
    payload: AIChatRequest,
    db=Depends(get_db),
    gemini=Depends(get_gemini),
    vector_search=Depends(get_vector_search),
):
    profile = await db.find_one("student_learning_profiles", {"student_id": payload.student_id}) or {}
    filters = {"subject": payload.subject} if payload.subject else {}
    retrieved = await vector_search.search(
        query=payload.question,
        collections=["notes", "tutors", "ai_reflections", "transcripts"],
        filters=filters,
        limit=6,
    )
    answer, is_mock = await gemini.generate_tutor_response(
        question=payload.question,
        student_profile=profile,
        retrieved_context=retrieved,
        language=payload.language,
    )
    conversation = {
        "student_id": payload.student_id,
        "question": payload.question,
        "answer": answer,
        "subject": payload.subject,
        "language": payload.language,
        "retrieved_context": [
            {
                "id": item["id"],
                "collection": item["collection"],
                "title": item["title"],
                "score": item["score"],
                "content_type": item["content_type"],
            }
            for item in retrieved
        ],
        "content_type": "ai_conversation",
    }
    conversation_id = await db.insert_one("ai_conversations", conversation)
    await db.update_one(
        "student_learning_profiles",
        {"student_id": payload.student_id},
        {"$push": {"recent_ai_questions": payload.question}},
        upsert=True,
    )
    return {"conversation_id": conversation_id, "answer": answer, "retrieved_context": conversation["retrieved_context"], "is_mock": is_mock}
