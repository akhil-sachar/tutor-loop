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
        "books",
        "book_chunks",
        "purchases",
        "bookings",
        "tutor_availability",
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
            "about_me": (
                "I am a calculus educator who specializes in reducing math anxiety with visual-first teaching.\n"
                "My sessions combine concept intuition, worked examples, and confidence-building checkpoints.\n"
                "I mentor first-year college students transitioning into proof-heavy and applied math courses.\n"
                "Students choose me when they want calm explanations and steady progress each week."
            ),
            "major_topics": [
                "Limits and continuity",
                "Derivative intuition and rules",
                "Optimization and related rates",
                "Integral setup and interpretation",
            ],
            "credentials": (
                "B.S. Applied Mathematics; M.Ed. Secondary Math Instruction.\n"
                "6+ years tutoring high school and undergraduate calculus.\n"
                "Former STEM learning-center coordinator and curriculum designer."
            ),
            "study_experience": "B.S. Applied Mathematics, University of Washington; M.Ed. in Mathematics Education.",
            "work_experience": "6+ years private tutoring, 2 years as STEM center coordinator, and AP Calculus workshop facilitator.",
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
            "about_me": (
                "I teach physics through motion stories, diagrams, and equation sense-making.\n"
                "My goal is to help students explain results verbally, not just compute answers.\n"
                "I support pre-med and engineering students who need practical problem-solving speed.\n"
                "Sessions are structured to convert weak spots into repeatable solving routines."
            ),
            "major_topics": [
                "Kinematics and motion graphs",
                "Forces and Newtonian dynamics",
                "Work-energy and power",
                "Calculus for physics applications",
            ],
            "credentials": (
                "B.S. Physics; M.S. Mechanical Engineering coursework.\n"
                "5+ years tutoring algebra-based and calculus-based physics.\n"
                "Industry experience in simulation-driven product testing."
            ),
            "study_experience": "B.S. Physics with graduate-level coursework in applied mechanics and numerical methods.",
            "work_experience": "Physics tutor for 5+ years and former simulation analyst in an engineering lab.",
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
            "about_me": (
                "I help students transform scattered notes into clear scientific writing and study systems.\n"
                "My approach blends active recall, outline design, and efficient revision cycles.\n"
                "I work with students balancing heavy reading loads across biology and writing courses.\n"
                "Lessons focus on clarity, retention, and confidence before exams and submissions."
            ),
            "major_topics": [
                "Biology concept mapping",
                "Lab report structure",
                "Evidence-based academic writing",
                "Exam revision strategy",
            ],
            "credentials": (
                "B.S. Biology; Graduate certificate in science communication.\n"
                "4+ years coaching research writing and pre-health coursework.\n"
                "Former peer-writing center mentor."
            ),
            "study_experience": "B.S. Biology plus postgraduate training in science communication and research writing.",
            "work_experience": "Writing center mentor and biology study coach supporting pre-health cohorts.",
            "hourly_rate": 34,
            "rating": 4.6,
            "teaching_style": "Turns broad confusion into outlines, flashcards, and retrieval practice.",
            "content_type": "tutor_profile",
        },
    ]
    for tutor in tutors:
        tutor["embedding"] = await vector_search.embed_document(
            tutor,
            [
                "display_name",
                "subjects",
                "bio",
                "about_me",
                "major_topics",
                "credentials",
                "study_experience",
                "work_experience",
                "teaching_style",
            ],
        )
        await db.insert_one("tutors", tutor)

    notes = [
        {
            "_id": "note-derivatives-visual",
            "tutor_id": DEMO_TUTOR_ID,
            "title": "Derivatives Without Panic",
            "subject": "Calculus",
            "description": (
                "Starts with secant lines and builds toward tangent-line intuition step by step.\n"
                "Shows how derivative rules connect to graph behavior and instant rate of change.\n"
                "Includes quick diagnostic checks to catch common sign and exponent mistakes.\n"
                "Designed for students who need a calm, visual first pass before harder problems."
            ),
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
            "description": (
                "Teaches a reliable process for identifying inner and outer functions quickly.\n"
                "Uses pattern families so students can classify expressions before differentiating.\n"
                "Provides common error examples and correction tips for nested functions.\n"
                "Ideal for timed quizzes where setup speed matters."
            ),
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
            "description": (
                "Explains how position, velocity, and acceleration graphs translate into motion stories.\n"
                "Focuses on slope, curvature, and sign analysis to avoid formula-only thinking.\n"
                "Includes graph interpretation prompts used in intro physics assessments.\n"
                "Great bridge for students combining calculus and mechanics."
            ),
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
        "purchased_book_ids": [],
        "session_ids": [],
        "ai_conversation_ids": [],
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
    now = datetime.now(timezone.utc).replace(minute=0, second=0, microsecond=0)
    starts_at = now + timedelta(days=1, hours=14 - now.hour)
    if starts_at <= now:
        starts_at = now + timedelta(days=1, hours=2)

    availability_id = "avail-demo-elena-booked"
    await db.insert_many(
        "tutor_availability",
        [
            {
                "_id": availability_id,
                "tutor_id": DEMO_TUTOR_ID,
                "subject": "Calculus",
                "topic": "Derivative intuition workshop",
                "starts_at": starts_at,
                "ends_at": starts_at + timedelta(minutes=30),
                "duration_minutes": 30,
                "status": "booked",
                "student_id": DEMO_STUDENT_ID,
            },
            {
                "_id": "avail-demo-elena-open-1",
                "tutor_id": DEMO_TUTOR_ID,
                "subject": "Calculus",
                "topic": "Chain rule fundamentals",
                "starts_at": starts_at + timedelta(hours=1),
                "ends_at": starts_at + timedelta(hours=1, minutes=30),
                "duration_minutes": 30,
                "status": "available",
            },
            {
                "_id": "avail-demo-elena-open-2",
                "tutor_id": DEMO_TUTOR_ID,
                "subject": "Calculus",
                "topic": "Tangent slope from limits",
                "starts_at": starts_at + timedelta(hours=2),
                "ends_at": starts_at + timedelta(hours=2, minutes=30),
                "duration_minutes": 30,
                "status": "available",
            },
            {
                "_id": "avail-demo-elena-blocked-1",
                "tutor_id": DEMO_TUTOR_ID,
                "subject": "Calculus",
                "topic": "Internal break",
                "starts_at": starts_at + timedelta(hours=3),
                "ends_at": starts_at + timedelta(hours=3, minutes=30),
                "duration_minutes": 30,
                "status": "blocked",
            },
            {
                "_id": "avail-demo-sam-open-1",
                "tutor_id": "tutor-demo-sam",
                "subject": "Physics",
                "topic": "Velocity from position graphs",
                "starts_at": starts_at + timedelta(hours=1),
                "ends_at": starts_at + timedelta(hours=1, minutes=30),
                "duration_minutes": 30,
                "status": "available",
            },
            {
                "_id": "avail-demo-sam-blocked-1",
                "tutor_id": "tutor-demo-sam",
                "subject": "Physics",
                "topic": "Unavailable",
                "starts_at": starts_at + timedelta(hours=2),
                "ends_at": starts_at + timedelta(hours=2, minutes=30),
                "duration_minutes": 30,
                "status": "blocked",
            },
            {
                "_id": "avail-demo-nina-open-1",
                "tutor_id": "tutor-demo-nina",
                "subject": "Biology",
                "topic": "Cell biology concept map",
                "starts_at": starts_at + timedelta(hours=1),
                "ends_at": starts_at + timedelta(hours=1, minutes=30),
                "duration_minutes": 30,
                "status": "available",
            },
        ],
    )
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
            "availability_slot_id": availability_id,
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
