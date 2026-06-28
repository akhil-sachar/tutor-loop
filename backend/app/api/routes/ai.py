import uuid

from fastapi import APIRouter, Depends, HTTPException

from backend.app.api.deps import get_db, get_gemini, get_learning, get_livekit, get_reflections, get_vector_search
from backend.app.db.mongo import utc_now
from backend.app.schemas.ai import (
    AIChatRequest,
    AIChatResponse,
    AILectureCompleteRequest,
    AILectureCompleteResponse,
    AILectureStartRequest,
    AILectureStartResponse,
    AIReflectRequest,
    AIReflectResponse,
    LectureNote,
)
from backend.app.schemas.learning import (
    ConversationFeedbackRequest,
    ConversationFeedbackResponse,
    QuizGradeRequest,
    QuizGradeResponse,
    QuizStartRequest,
    QuizStartResponse,
)

router = APIRouter(prefix="/ai", tags=["ai"])

AI_RETRIEVAL_COLLECTIONS = [
    "books",
    "book_chunks",
    "notes",
    "tutors",
    "ai_reflections",
    "transcripts",
    "ai_conversations",
]

LECTURE_OUTLINE = [
    "Warm-up: connect the topic to what you already know",
    "Core concept with a visual intuition",
    "Worked example from your notes or textbook",
    "Pause for your questions — speak anytime to interject",
    "Quick check and summary of what to practice next",
]


def _lecture_notes_from_results(results: list[dict]) -> list[LectureNote]:
    notes: list[LectureNote] = []
    seen: set[str] = set()
    for item in results:
        item_id = str(item.get("id") or item.get("_id"))
        if item_id in seen:
            continue
        seen.add(item_id)
        notes.append(
            LectureNote(
                id=item_id,
                title=str(item.get("title", "Resource")),
                subject=item.get("subject"),
                snippet=str(item.get("snippet") or item.get("content") or item.get("description") or "")[:320],
                source=str(item.get("collection") or item.get("content_type") or "resource"),
            )
        )
    return notes


@router.post("/lecture/start", response_model=AILectureStartResponse)
async def start_ai_lecture(
    payload: AILectureStartRequest,
    db=Depends(get_db),
    livekit=Depends(get_livekit),
    vector_search=Depends(get_vector_search),
):
    profile = await db.find_one("student_learning_profiles", {"student_id": payload.student_id}) or {}
    query = f"{payload.subject} {payload.topic} {' '.join(profile.get('weak_topics', [])[:4])}"

    grounded_sources = bool(payload.note_ids or payload.book_ids)
    if grounded_sources:
        # RAG narrowing: ground the lecture only on the selected notes/books.
        retrieved = await vector_search.search_sources(
            query=query,
            note_ids=payload.note_ids,
            book_ids=payload.book_ids,
            limit=10,
        )
    else:
        # Book CONTENT comes only from the content/ folder (books + book_chunks),
        # but the tutor still learns from its own memory: prior session reflections
        # and transcripts. Marketplace notes are intentionally excluded. Rank purely
        # by semantic similarity (no exact-subject filter) so any topic works.
        retrieved = await vector_search.search(
            query=query,
            collections=["books", "book_chunks", "ai_reflections", "transcripts"],
            filters={},
            limit=8,
        )
    lecture_notes = _lecture_notes_from_results(retrieved)

    lecture_id = f"lecture-{payload.student_id[:8]}-{uuid.uuid4().hex[:10]}"
    room_id = livekit.room_id_for_ai_lecture(lecture_id)
    agent_metadata = {
        "lecture_id": lecture_id,
        "student_id": payload.student_id,
        "subject": payload.subject,
        "topic": payload.topic,
        "language": payload.language,
        "weak_topics": profile.get("weak_topics", [])[:6],
        "future_ai_instructions": profile.get("future_ai_instructions", [])[:6],
        "lecture_notes": [note.model_dump() for note in lecture_notes],
        "lecture_outline": LECTURE_OUTLINE,
        "grounded_sources": grounded_sources,
    }
    token_payload = livekit.create_ai_lecture_token(
        room_id=room_id,
        identity=payload.student_id,
        display_name="Student",
        agent_metadata=agent_metadata,
    )

    await db.insert_one(
        "ai_lecture_sessions",
        {
            "_id": lecture_id,
            "student_id": payload.student_id,
            "subject": payload.subject,
            "topic": payload.topic,
            "room_id": room_id,
            "status": "live",
            "notes": [note.model_dump() for note in lecture_notes],
            "agent_metadata": agent_metadata,
            "content_type": "ai_lecture",
            "created_at": utc_now(),
        },
    )

    return {
        "lecture_id": lecture_id,
        "room_id": room_id,
        "room_url": token_payload["room_url"],
        "token": token_payload["token"],
        "is_mock": token_payload["is_mock"],
        "agent_name": token_payload.get("agent_name"),
        "notes": lecture_notes,
        "lecture_outline": LECTURE_OUTLINE,
        "grounded_sources": grounded_sources,
    }


@router.post("/lecture/{lecture_id}/complete", response_model=AILectureCompleteResponse)
async def complete_ai_lecture(
    lecture_id: str,
    payload: AILectureCompleteRequest,
    db=Depends(get_db),
    vector_search=Depends(get_vector_search),
):
    lecture = await db.find_one("ai_lecture_sessions", {"_id": lecture_id})
    if not lecture:
        raise HTTPException(status_code=404, detail="Lecture session not found")

    existing_conversation_id = lecture.get("conversation_id")
    conversation = {
        "student_id": payload.student_id,
        "question": lecture.get("topic", "AI lecture"),
        "answer": payload.transcript,
        "subject": lecture.get("subject"),
        "language": "English",
        "status": "completed",
        "session_type": "live_lecture",
        "lecture_id": lecture_id,
        "content_type": "ai_conversation",
        "created_at": utc_now(),
    }
    conversation["embedding"] = await vector_search.embed_document(
        conversation,
        ["subject", "question", "answer"],
    )
    if existing_conversation_id:
        conversation_id = existing_conversation_id
        await db.update_one(
            "ai_conversations",
            {"_id": conversation_id},
            {"$set": conversation},
        )
    else:
        conversation_id = await db.insert_one("ai_conversations", conversation)
    await db.update_one(
        "ai_lecture_sessions",
        {"_id": lecture_id},
        {"$set": {"status": "completed", "conversation_id": conversation_id, "transcript": payload.transcript}},
    )
    return {
        "lecture_id": lecture_id,
        "conversation_id": conversation_id,
        "message": "Lecture saved. Reflect on this session to update the AI tutor memory.",
    }


@router.post("/chat", response_model=AIChatResponse)
async def ai_chat(
    payload: AIChatRequest,
    db=Depends(get_db),
    gemini=Depends(get_gemini),
    vector_search=Depends(get_vector_search),
):
    profile = await db.find_one("student_learning_profiles", {"student_id": payload.student_id}) or {}
    if payload.note_ids or payload.book_ids:
        # RAG narrowing: answer using only the student's selected sources.
        retrieved = await vector_search.search_sources(
            query=payload.question,
            note_ids=payload.note_ids,
            book_ids=payload.book_ids,
            limit=8,
        )
    else:
        filters = {"subject": payload.subject} if payload.subject else {}
        retrieved = await vector_search.search(
            query=payload.question,
            collections=AI_RETRIEVAL_COLLECTIONS,
            filters=filters,
            limit=8,
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
        "status": "completed",
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
        "created_at": utc_now(),
    }
    conversation["embedding"] = await vector_search.embed_document(
        conversation,
        ["subject", "question", "answer"],
    )
    conversation_id = await db.insert_one("ai_conversations", conversation)
    await db.update_one(
        "student_learning_profiles",
        {"student_id": payload.student_id},
        {"$push": {"recent_ai_questions": payload.question}},
        upsert=True,
    )
    return {
        "conversation_id": conversation_id,
        "answer": answer,
        "retrieved_context": conversation["retrieved_context"],
        "is_mock": is_mock,
    }


@router.post("/conversations/{conversation_id}/reflect", response_model=AIReflectResponse)
async def reflect_ai_conversation(
    conversation_id: str,
    payload: AIReflectRequest,
    reflections=Depends(get_reflections),
):
    try:
        return await reflections.reflect_ai_conversation(
            conversation_id=conversation_id,
            target_language=payload.target_language,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/quiz/start", response_model=QuizStartResponse)
async def start_quiz(payload: QuizStartRequest, learning=Depends(get_learning)):
    return await learning.start_quiz(
        student_id=payload.student_id,
        subject=payload.subject,
        topic=payload.topic,
        num_questions=payload.num_questions,
    )


@router.post("/quiz/grade", response_model=QuizGradeResponse)
async def grade_quiz(payload: QuizGradeRequest, learning=Depends(get_learning)):
    try:
        return await learning.grade_quiz(
            quiz_id=payload.quiz_id,
            answers=[answer.model_dump() for answer in payload.answers],
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/conversations/{conversation_id}/feedback", response_model=ConversationFeedbackResponse)
async def conversation_feedback(
    conversation_id: str,
    payload: ConversationFeedbackRequest,
    learning=Depends(get_learning),
):
    try:
        return await learning.record_feedback(
            conversation_id=conversation_id,
            student_id=payload.student_id,
            helpful=payload.helpful,
            note=payload.note,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
