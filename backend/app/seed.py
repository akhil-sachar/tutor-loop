from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from typing import Any

from backend.app.core.config import get_settings
from backend.app.core.security import hash_password
from backend.app.db.mongo import AppDatabase, utc_now
from backend.app.services.gemini_service import GeminiService
from backend.app.services.vector_search import VectorSearchService


DEMO_STUDENT_ID = "student-demo-maya"
DEMO_TUTOR_ID = "tutor-demo-elena"
DEMO_TUTOR_USER_ID = "user-demo-elena"


async def seed_demo_data(db: Any, gemini: Any, vector_search: Any, *, reset: bool = False) -> dict[str, Any]:
    collections = [
        "users",
        "tutors",
        "notes",
        "purchases",
        "bookings",
        "sessions",
        "transcripts",
        "ai_conversations",
        "ai_reflections",
        "student_learning_profiles",
        "recommendations",
        "reviews",
    ]
    if reset:
        for collection in collections:
            await db.delete_many(collection, {})

    if await db.count_documents("users", {}) > 0:
        return {"seeded": False, "message": "Demo data already exists"}

    await db.insert_many(
        "users",
        [
            {
                "_id": DEMO_STUDENT_ID,
                "name": "Maya Chen",
                "email": "student@tutorloop.demo",
                "password_hash": hash_password("password123"),
                "role": "student",
                "subjects": ["Calculus", "Physics"],
                "bio": "First-year college student building confidence in calculus.",
            },
            {
                "_id": DEMO_TUTOR_USER_ID,
                "name": "Elena Rivera",
                "email": "tutor@tutorloop.demo",
                "password_hash": hash_password("password123"),
                "role": "tutor",
                "subjects": ["Calculus", "Algebra"],
                "bio": "Math tutor who teaches with visual intuition first.",
            },
        ],
    )

    tutors = [
        {
            "_id": DEMO_TUTOR_ID,
            "user_id": DEMO_TUTOR_USER_ID,
            "display_name": "Elena Rivera",
            "subjects": ["Calculus", "Algebra", "Precalculus"],
            "bio": "Patient calculus tutor focused on graphs, intuition, and quick checks for understanding.",
            "hourly_rate": 42,
            "rating": 4.9,
            "teaching_style": "Graph-first, step-by-step explanations, frequent concept checks, and calm correction.",
            "content_type": "tutor_profile",
        },
        {
            "_id": "tutor-demo-sam",
            "user_id": "user-demo-sam",
            "display_name": "Sam Okafor",
            "subjects": ["Physics", "Calculus"],
            "bio": "Physics tutor who connects derivatives to velocity, acceleration, and real motion examples.",
            "hourly_rate": 38,
            "rating": 4.7,
            "teaching_style": "Uses concrete physics scenarios and short quizzes to reveal misconceptions.",
            "content_type": "tutor_profile",
        },
        {
            "_id": "tutor-demo-nina",
            "user_id": "user-demo-nina",
            "display_name": "Nina Patel",
            "subjects": ["Writing", "Biology"],
            "bio": "Study coach for lab reports, essays, and biology concept maps.",
            "hourly_rate": 34,
            "rating": 4.6,
            "teaching_style": "Turns broad confusion into outlines, flashcards, and retrieval practice.",
            "content_type": "tutor_profile",
        },
    ]
    for tutor in tutors:
        tutor["embedding"] = await vector_search.embed_document(tutor, ["display_name", "subjects", "bio", "teaching_style"])
        await db.insert_one("tutors", tutor)

    notes = [
        {
            "_id": "note-derivatives-visual",
            "tutor_id": DEMO_TUTOR_ID,
            "title": "Derivatives Without Panic",
            "subject": "Calculus",
            "description": "A visual guide to secant slopes, tangent lines, and the power rule.",
            "price": 9.0,
            "content": "Derivatives measure instant rate of change. Start with secant slope, move the second point closer, and watch the tangent slope emerge. Includes f(x)=x^2 examples and quick checks.",
            "rating": 4.8,
            "purchases_count": 12,
            "content_type": "note",
        },
        {
            "_id": "note-chain-rule",
            "tutor_id": DEMO_TUTOR_ID,
            "title": "Chain Rule Pattern Sheet",
            "subject": "Calculus",
            "description": "How to spot inside and outside functions before differentiating.",
            "price": 7.5,
            "content": "The chain rule works when one function is nested inside another. Mark the outside, mark the inside, differentiate outside, then multiply by the derivative of inside.",
            "rating": 4.6,
            "purchases_count": 9,
            "content_type": "note",
        },
        {
            "_id": "note-physics-motion",
            "tutor_id": "tutor-demo-sam",
            "title": "Velocity and Acceleration From Graphs",
            "subject": "Physics",
            "description": "Use slope and curvature to reason about motion graphs.",
            "price": 8.0,
            "content": "Velocity is the derivative of position. Acceleration is the derivative of velocity. Graph slope tells a story about motion.",
            "rating": 4.7,
            "purchases_count": 6,
            "content_type": "note",
        },
    ]
    for note in notes:
        note["embedding"] = await vector_search.embed_document(note, ["title", "subject", "description", "content"])
        await db.insert_one("notes", note)

    profile = {
        "_id": DEMO_STUDENT_ID,
        "student_id": DEMO_STUDENT_ID,
        "primary_subject": "Calculus",
        "weak_topics": ["derivatives as instant rate of change", "secant slope to tangent slope"],
        "mastered_topics": ["basic algebra"],
        "learning_style": "visual, step-by-step",
        "purchased_note_ids": [],
        "session_ids": [],
        "reflection_ids": [],
        "future_ai_instructions": [
            "Use graph intuition before derivative rules.",
            "Ask a short check question after each worked example.",
        ],
        "successful_teaching_methods": ["graph-first explanations"],
        "content_type": "student_profile",
        "created_at": utc_now(),
        "updated_at": utc_now(),
    }
    profile["recommendation_vector"] = await gemini.embed_text("derivatives graph slope tangent visual step-by-step")
    await db.insert_one("student_learning_profiles", profile)

    booking_id = "booking-demo-derivatives"
    session_id = "session-demo-derivatives"
    starts_at = datetime.now(timezone.utc) + timedelta(hours=2)
    await db.insert_one(
        "bookings",
        {
            "_id": booking_id,
            "tutor_id": DEMO_TUTOR_ID,
            "student_id": DEMO_STUDENT_ID,
            "subject": "Calculus",
            "starts_at": starts_at,
            "duration_minutes": 45,
            "status": "booked",
            "room_id": "tutorloop-booking-derivatives",
            "session_id": session_id,
        },
    )
    await db.insert_one(
        "sessions",
        {
            "_id": session_id,
            "booking_id": booking_id,
            "tutor_id": DEMO_TUTOR_ID,
            "student_id": DEMO_STUDENT_ID,
            "subject": "Calculus",
            "room_id": "tutorloop-booking-derivatives",
            "status": "booked",
            "content_type": "lesson_summary",
        },
    )

    return {
        "seeded": True,
        "student_id": DEMO_STUDENT_ID,
        "tutor_id": DEMO_TUTOR_ID,
        "booking_id": booking_id,
        "session_id": session_id,
    }


async def main() -> None:
    settings = get_settings()
    db = AppDatabase(settings)
    await db.connect()
    gemini = GeminiService(settings)
    vector_search = VectorSearchService(db, gemini, settings)
    result = await seed_demo_data(db, gemini, vector_search, reset=True)
    print(result)
    await db.close()


if __name__ == "__main__":
    asyncio.run(main())
