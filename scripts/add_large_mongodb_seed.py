from __future__ import annotations

import argparse
import asyncio
import random
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from backend.app.core.config import get_settings
from backend.app.core.security import hash_password
from backend.app.db.mongo import AppDatabase, utc_now
from backend.app.services.gemini_service import GeminiService
from backend.app.services.vector_search import VectorSearchService


BATCH_ID = "bulk-demo-v1"
DEFAULT_TUTOR_COUNT = 750
DEFAULT_STUDENT_COUNT = 360
DEFAULT_SESSION_COUNT = 1500
DEFAULT_BOOK_COUNT = 650
DEFAULT_NOTE_COUNT = 820
DEFAULT_PURCHASE_COUNT = 2400
DEFAULT_SLOTS_PER_TUTOR = 12

BULK_COLLECTIONS = [
    "users",
    "tutors",
    "student_learning_profiles",
    "books",
    "book_chunks",
    "notes",
    "tutor_availability",
    "bookings",
    "sessions",
    "tutor_session_history",
    "transcripts",
    "reviews",
    "purchases",
    "purchase_history",
]

FIRST_NAMES = [
    "Aarav",
    "Aisha",
    "Amara",
    "Andre",
    "Anika",
    "Arjun",
    "Camila",
    "Chloe",
    "Daniel",
    "Elena",
    "Fatima",
    "Grace",
    "Hana",
    "Iris",
    "Jamal",
    "Kai",
    "Leah",
    "Mateo",
    "Maya",
    "Noah",
    "Priya",
    "Ravi",
    "Sam",
    "Sofia",
    "Theo",
    "Valeria",
    "Yara",
    "Zane",
]

LAST_NAMES = [
    "Bennett",
    "Chen",
    "Garcia",
    "Hassan",
    "Ito",
    "Johnson",
    "Khan",
    "Kim",
    "Kumar",
    "Lopez",
    "Miller",
    "Nguyen",
    "Okafor",
    "Patel",
    "Rivera",
    "Santos",
    "Shah",
    "Singh",
    "Smith",
    "Tan",
    "Williams",
    "Zhang",
]

SUBJECT_AREAS = [
    {
        "subject": "Calculus",
        "categories": ["STEM", "Mathematics", "College Prep"],
        "topics": [
            "derivatives",
            "limits",
            "chain rule",
            "integrals",
            "related rates",
            "optimization",
            "tangent lines",
            "area under curves",
        ],
    },
    {
        "subject": "Algebra",
        "categories": ["STEM", "Mathematics", "Foundations"],
        "topics": [
            "linear equations",
            "quadratics",
            "factoring",
            "systems of equations",
            "inequalities",
            "exponents",
            "functions",
        ],
    },
    {
        "subject": "Physics",
        "categories": ["STEM", "Science", "AP Prep"],
        "topics": [
            "kinematics",
            "forces",
            "energy",
            "momentum",
            "electric fields",
            "waves",
            "velocity graphs",
        ],
    },
    {
        "subject": "Chemistry",
        "categories": ["STEM", "Science", "Lab Skills"],
        "topics": [
            "stoichiometry",
            "moles",
            "bonding",
            "acid base reactions",
            "thermodynamics",
            "equilibrium",
            "periodic trends",
        ],
    },
    {
        "subject": "Biology",
        "categories": ["Science", "Pre-Med", "AP Prep"],
        "topics": [
            "cell structure",
            "genetics",
            "evolution",
            "photosynthesis",
            "enzymes",
            "ecology",
            "human physiology",
        ],
    },
    {
        "subject": "Statistics",
        "categories": ["STEM", "Data", "College Prep"],
        "topics": [
            "probability",
            "hypothesis testing",
            "confidence intervals",
            "regression",
            "normal distribution",
            "sampling",
            "p-values",
        ],
    },
    {
        "subject": "Computer Science",
        "categories": ["STEM", "Programming", "Career Skills"],
        "topics": [
            "Python loops",
            "recursion",
            "data structures",
            "algorithms",
            "Big O",
            "debugging",
            "AP CSP",
        ],
    },
    {
        "subject": "Writing",
        "categories": ["Humanities", "Communication", "College Prep"],
        "topics": [
            "thesis statements",
            "essay structure",
            "evidence integration",
            "argumentation",
            "grammar",
            "revision",
            "research writing",
        ],
    },
]

TEACHING_STYLES = [
    "graph-first explanations with short checks for understanding",
    "Socratic questioning followed by a worked example",
    "visual diagrams, color-coded steps, and retrieval practice",
    "exam-style problem solving with misconception repair",
    "story-based explanations connected to real-world examples",
    "guided practice that fades support one step at a time",
]

DIFFICULTIES = ["Beginner", "Intermediate", "Advanced", "AP", "College"]


def slug(value: str) -> str:
    return "-".join(part for part in "".join(character.lower() if character.isalnum() else " " for character in value).split() if part)


def pick_area(index: int, rng: random.Random) -> dict[str, Any]:
    if index % 5 == 0:
        return SUBJECT_AREAS[0]
    return rng.choice(SUBJECT_AREAS)


def pick_topics(area: dict[str, Any], rng: random.Random, *, count: int = 3) -> list[str]:
    topics = area["topics"]
    return rng.sample(topics, k=min(count, len(topics)))


def timestamp(offset_days: int, hour: int, minute: int = 0) -> datetime:
    base = datetime.now(timezone.utc).replace(hour=hour, minute=minute, second=0, microsecond=0)
    return base - timedelta(days=offset_days)


async def add_embeddings(vector_search: VectorSearchService, collection: str, docs: list[dict[str, Any]]) -> None:
    fields_by_collection = {
        "tutors": ["display_name", "subjects", "bio", "teaching_style", "topics", "categories"],
        "books": ["title", "subject", "description", "topics", "categories", "table_of_contents"],
        "book_chunks": ["title", "subject", "content", "topics", "categories"],
        "notes": ["title", "subject", "description", "content", "topics", "categories"],
        "sessions": ["subject", "topic", "summary", "student_questions", "successful_teaching_methods"],
        "transcripts": ["subject", "topic", "transcript", "summary"],
    }
    fields = fields_by_collection.get(collection)
    if not fields:
        return
    for doc in docs:
        doc["embedding"] = await vector_search.embed_document(doc, fields)


async def insert_chunked(db: AppDatabase, collection: str, docs: list[dict[str, Any]], *, chunk_size: int = 250) -> int:
    if not docs:
        return 0
    inserted = 0
    for start in range(0, len(docs), chunk_size):
        chunk = docs[start : start + chunk_size]
        if db.is_mongo:
            await db.collection(collection).insert_many(chunk, ordered=False)
            inserted += len(chunk)
        else:
            await db.insert_many(collection, chunk)
            inserted += len(chunk)
    return inserted


async def connect_mongo(settings: Any, *, timeout_ms: int) -> AppDatabase:
    db = AppDatabase(settings)
    from motor.motor_asyncio import AsyncIOMotorClient

    try:
        db.client = AsyncIOMotorClient(
            settings.mongodb_uri,
            serverSelectionTimeoutMS=timeout_ms,
            connectTimeoutMS=timeout_ms,
            socketTimeoutMS=timeout_ms,
        )
        db.db = db.client[settings.mongodb_db_name]
        await db.db.command("ping")
        return db
    except Exception as exc:
        db.connection_error = str(exc)
        if db.client:
            db.client.close()
        db.client = None
        db.db = None
        return db


def build_users_and_tutors(tutor_count: int, student_count: int, rng: random.Random) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    users: list[dict[str, Any]] = []
    tutors: list[dict[str, Any]] = []
    students: list[dict[str, Any]] = []
    now = utc_now()

    for index in range(student_count):
        area = pick_area(index, rng)
        first = FIRST_NAMES[index % len(FIRST_NAMES)]
        last = LAST_NAMES[(index * 7) % len(LAST_NAMES)]
        user_id = f"bulk-student-{index + 1:04d}"
        student = {
            "_id": user_id,
            "name": f"{first} {last}",
            "email": f"student{index + 1:04d}@tutorloop.demo",
            "password_hash": hash_password("password123"),
            "role": "student",
            "subjects": [area["subject"]],
            "bio": f"Student practicing {area['subject']} with focus on {', '.join(area['topics'][:3])}.",
            "grade_level": rng.choice(["High School", "AP", "College", "Adult Learner"]),
            "learning_goals": pick_topics(area, rng, count=3),
            "profile_rating": round(3.7 + (index % 120) / 100, 2),
            "average_session_rating": round(4.0 + (index % 90) / 100, 2),
            "timezone": rng.choice(["America/Los_Angeles", "America/New_York", "America/Chicago", "America/Denver"]),
            "preferred_language": rng.choice(["English", "Spanish", "Hindi", "French", "Mandarin"]),
            "study_streak_days": 2 + (index % 42),
            "completed_sessions_count": 2 + (index % 18),
            "account_status": "active",
            "seed_batch": BATCH_ID,
            "created_at": now,
            "updated_at": now,
        }
        users.append(student)
        students.append(student)

    for index in range(tutor_count):
        primary = pick_area(index, rng)
        secondary = rng.choice([area for area in SUBJECT_AREAS if area != primary])
        topics = pick_topics(primary, rng, count=4) + pick_topics(secondary, rng, count=2)
        first = FIRST_NAMES[(index * 3) % len(FIRST_NAMES)]
        last = LAST_NAMES[(index * 5) % len(LAST_NAMES)]
        user_id = f"bulk-tutor-user-{index + 1:04d}"
        tutor_id = f"bulk-tutor-{index + 1:04d}"
        rating = round(4.15 + (index % 80) / 100, 2)
        hourly_rate = 22 + (index % 49)
        users.append(
            {
                "_id": user_id,
                "name": f"{first} {last}",
                "email": f"tutor{index + 1:04d}@tutorloop.demo",
                "password_hash": hash_password("password123"),
                "role": "tutor",
                "subjects": [primary["subject"], secondary["subject"]],
                "bio": f"Tutor for {primary['subject']} and {secondary['subject']} with practice on {', '.join(topics[:4])}.",
                "profile_rating": rating,
                "average_session_rating": rating,
                "timezone": rng.choice(["America/Los_Angeles", "America/New_York", "America/Chicago", "America/Denver"]),
                "preferred_language": rng.choice(["English", "Spanish", "Hindi", "French", "Mandarin"]),
                "account_status": "active",
                "seed_batch": BATCH_ID,
                "created_at": now,
                "updated_at": now,
            }
        )
        tutors.append(
            {
                "_id": tutor_id,
                "user_id": user_id,
                "display_name": f"{first} {last}",
                "subjects": [primary["subject"], secondary["subject"]],
                "primary_subject": primary["subject"],
                "bio": (
                    f"{primary['subject']} tutor who helps students move from confusion to practice-ready confidence. "
                    f"Common sessions cover {', '.join(topics[:5])}."
                ),
                "hourly_rate": float(hourly_rate),
                "rating": rating,
                "review_count": 18 + (index % 130),
                "years_experience": 2 + (index % 14),
                "teaching_style": TEACHING_STYLES[index % len(TEACHING_STYLES)],
                "topics": topics,
                "categories": sorted(set(primary["categories"] + secondary["categories"])),
                "languages": rng.sample(["English", "Spanish", "Hindi", "French", "Mandarin"], k=2),
                "availability": rng.sample(["weekday evenings", "weekend mornings", "after school", "late night review"], k=2),
                "session_highlights": [
                    f"Explains {topics[0]} using concrete examples",
                    f"Builds quizzes for {topics[1]} misconceptions",
                    f"Adapts practice around {topics[2]} weak spots",
                ],
                "content_type": "tutor_profile",
                "seed_batch": BATCH_ID,
                "created_at": now,
                "updated_at": now,
            }
        )

    return users, tutors, students


def build_books(book_count: int, rng: random.Random) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    books: list[dict[str, Any]] = []
    chunks: list[dict[str, Any]] = []
    now = utc_now()

    for index in range(book_count):
        area = pick_area(index, rng)
        topics = pick_topics(area, rng, count=4)
        difficulty = DIFFICULTIES[index % len(DIFFICULTIES)]
        title = f"{area['subject']} Tutor Guide {index + 1:04d}: {topics[0].title()} and {topics[1].title()}"
        book_id = f"bulk-book-{index + 1:04d}"
        pages = 72 + (index * 7) % 430
        price = round(4.99 + ((index * 37) % 3600) / 100, 2)
        table_of_contents = [
            f"Chapter 1: Core intuition for {topics[0]}",
            f"Chapter 2: Guided examples for {topics[1]}",
            f"Chapter 3: Common mistakes in {topics[2]}",
            f"Chapter 4: Practice quiz for {topics[3]}",
        ]
        description = (
            f"A {difficulty.lower()} {area['subject']} book for tutoring sessions. "
            f"Covers {', '.join(topics)} with worked examples, checks for understanding, "
            "weak-topic repair prompts, and retrieval-practice questions."
        )
        books.append(
            {
                "_id": book_id,
                "title": title,
                "slug": slug(title),
                "subject": area["subject"],
                "category": area["categories"][0],
                "categories": area["categories"],
                "topics": topics,
                "description": description,
                "author": f"TutorLoop Faculty {index % 37 + 1}",
                "publisher": "TutorLoop Demo Press",
                "edition": f"{2023 + (index % 4)} Hackathon Edition",
                "difficulty": difficulty,
                "price": price,
                "pages": pages,
                "rating": round(4.05 + (index % 90) / 100, 2),
                "review_count": 8 + (index % 220),
                "table_of_contents": table_of_contents,
                "learning_objectives": [
                    f"Explain {topics[0]} in plain language",
                    f"Solve scaffolded problems about {topics[1]}",
                    f"Diagnose misconceptions around {topics[2]}",
                ],
                "semantic_keywords": sorted(set(topics + area["categories"] + [area["subject"], difficulty, "tutoring", "practice"])),
                "content_type": "book",
                "seed_batch": BATCH_ID,
                "created_at": now,
                "updated_at": now,
            }
        )
        chunks.append(
            {
                "_id": f"{book_id}-chunk-001",
                "book_id": book_id,
                "title": title,
                "subject": area["subject"],
                "category": area["categories"][0],
                "categories": area["categories"],
                "topics": topics,
                "chunk_index": 1,
                "page_start": 1 + (index % max(pages - 8, 1)),
                "page_end": min(pages, 8 + (index % max(pages - 8, 1))),
                "content": (
                    f"{title}. This excerpt teaches {topics[0]} by connecting definitions, diagrams, "
                    f"worked examples, student questions, and a short quiz. It also links {topics[1]} "
                    f"to prior knowledge and flags common confusion around {topics[2]}."
                ),
                "content_type": "book_chunk",
                "seed_batch": BATCH_ID,
                "created_at": now,
                "updated_at": now,
            }
        )

    return books, chunks


def build_notes(note_count: int, tutors: list[dict[str, Any]], rng: random.Random) -> list[dict[str, Any]]:
    notes: list[dict[str, Any]] = []
    now = utc_now()

    for index in range(note_count):
        tutor = tutors[index % len(tutors)]
        subject = tutor["primary_subject"]
        area = next(area for area in SUBJECT_AREAS if area["subject"] == subject)
        topics = pick_topics(area, rng, count=4)
        title = f"{subject} Chalk Notes {index + 1:04d}: {topics[0].title()} Sprint"
        pages = 3 + (index * 5) % 58
        price = round(1.99 + ((index * 19) % 2100) / 100, 2)
        notes.append(
            {
                "_id": f"bulk-note-{index + 1:04d}",
                "tutor_id": tutor["_id"],
                "title": title,
                "slug": slug(title),
                "subject": subject,
                "category": area["categories"][0],
                "categories": area["categories"],
                "topics": topics,
                "description": (
                    f"Concise tutor notes for {subject} covering {', '.join(topics)}. "
                    "Designed for semantic retrieval, quick review, and AI tutor grounding."
                ),
                "content": (
                    f"These notes teach {topics[0]} with a warm-up question, a visual explanation, "
                    f"two worked examples, a mistake clinic for {topics[1]}, and a mini quiz covering "
                    f"{topics[2]} and {topics[3]}. Tutor style: {tutor['teaching_style']}."
                ),
                "price": price,
                "pages": pages,
                "estimated_read_minutes": max(5, pages * 2),
                "difficulty": DIFFICULTIES[index % len(DIFFICULTIES)],
                "rating": round(4.0 + (index % 95) / 100, 2),
                "purchases_count": 3 + (index % 340),
                "semantic_keywords": sorted(set(topics + area["categories"] + [subject, "notes", "quiz", "worked examples"])),
                "content_type": "note",
                "seed_batch": BATCH_ID,
                "created_at": now,
                "updated_at": now,
            }
        )

    return notes


def build_availability(tutors: list[dict[str, Any]], slots_per_tutor: int) -> list[dict[str, Any]]:
    availability: list[dict[str, Any]] = []
    now = utc_now()
    base = (now + timedelta(days=1)).replace(hour=9, minute=0, second=0, microsecond=0)

    for tutor_index, tutor in enumerate(tutors):
        area = next(area for area in SUBJECT_AREAS if area["subject"] == tutor["primary_subject"])
        for slot_index in range(slots_per_tutor):
            day_offset = slot_index // 8
            minute_offset = (slot_index % 8) * 30
            starts_at = base + timedelta(days=(tutor_index % 6) + day_offset, hours=(tutor_index % 4), minutes=minute_offset)
            ends_at = starts_at + timedelta(minutes=30)
            topic = area["topics"][(tutor_index + slot_index) % len(area["topics"])]
            availability.append(
                {
                    "_id": f"bulk-slot-{tutor_index + 1:04d}-{slot_index + 1:03d}",
                    "tutor_id": tutor["_id"],
                    "tutor_user_id": tutor["user_id"],
                    "tutor_name": tutor["display_name"],
                    "subject": tutor["primary_subject"],
                    "topic": topic,
                    "starts_at": starts_at,
                    "ends_at": ends_at,
                    "duration_minutes": 30,
                    "status": "available",
                    "timezone": "UTC",
                    "slot_type": "live_tutoring",
                    "content_type": "tutor_availability",
                    "seed_batch": BATCH_ID,
                    "created_at": now,
                    "updated_at": now,
                }
            )

    return availability


def build_purchases(
    purchase_count: int,
    students: list[dict[str, Any]],
    notes: list[dict[str, Any]],
    books: list[dict[str, Any]],
    rng: random.Random,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, dict[str, list[str]]]]:
    purchases: list[dict[str, Any]] = []
    purchase_history: list[dict[str, Any]] = []
    purchased_by_student: dict[str, dict[str, list[str]]] = {}
    now = utc_now()

    for index in range(purchase_count):
        student = students[(index * 17) % len(students)]
        student_id = student["_id"]
        purchased_by_student.setdefault(student_id, {"notes": [], "books": []})
        is_note = index % 2 == 0
        item = notes[(index * 13) % len(notes)] if is_note else books[(index * 7) % len(books)]
        item_type = "note" if is_note else "book"
        purchase_id = f"bulk-purchase-{index + 1:05d}"
        purchased_at = now - timedelta(days=1 + (index % 420), hours=index % 12)
        amount = float(item.get("price", 0))
        common = {
            "_id": purchase_id,
            "student_id": student_id,
            "student_name": student["name"],
            "student_email": student["email"],
            "item_type": item_type,
            "item_id": item["_id"],
            "title": item["title"],
            "subject": item["subject"],
            "category": item.get("category"),
            "categories": item.get("categories", []),
            "topics": item.get("topics", []),
            "amount": amount,
            "price": amount,
            "currency": "USD",
            "status": "simulated_paid",
            "payment_provider": "mock",
            "purchased_at": purchased_at,
            "rating_after_purchase": round(4.0 + (index % 100) / 100, 2),
            "content_type": "purchase",
            "seed_batch": BATCH_ID,
            "created_at": purchased_at,
            "updated_at": now,
        }
        if is_note:
            common["note_id"] = item["_id"]
            common["tutor_id"] = item["tutor_id"]
            purchased_by_student[student_id]["notes"].append(item["_id"])
        else:
            common["book_id"] = item["_id"]
            common["pages"] = item.get("pages")
            purchased_by_student[student_id]["books"].append(item["_id"])

        purchases.append(common)
        purchase_history.append(
            {
                **common,
                "_id": f"bulk-purchase-history-{index + 1:05d}",
                "purchase_id": purchase_id,
                "content_type": "purchase_history",
            }
        )

    return purchases, purchase_history, purchased_by_student


async def build_student_profiles(
    students: list[dict[str, Any]],
    sessions: list[dict[str, Any]],
    purchased_by_student: dict[str, dict[str, list[str]]],
    vector_search: VectorSearchService,
) -> list[dict[str, Any]]:
    profiles: list[dict[str, Any]] = []
    now = utc_now()
    session_ids_by_student: dict[str, list[str]] = {}
    weak_topics_by_student: dict[str, list[str]] = {}

    for session in sessions:
        student_id = session["student_id"]
        session_ids_by_student.setdefault(student_id, []).append(session["_id"])
        weak_topics_by_student.setdefault(student_id, []).extend(session.get("weak_topics", []))

    for index, student in enumerate(students):
        subject = student["subjects"][0]
        area = next(area for area in SUBJECT_AREAS if area["subject"] == subject)
        purchases = purchased_by_student.get(student["_id"], {"notes": [], "books": []})
        weak_topics = list(dict.fromkeys((weak_topics_by_student.get(student["_id"]) or area["topics"])[:6]))
        mastered_topics = [topic for topic in area["topics"] if topic not in weak_topics][:3]
        profile = {
            "_id": student["_id"],
            "student_id": student["_id"],
            "name": student["name"],
            "email": student["email"],
            "primary_subject": subject,
            "weak_topics": weak_topics,
            "mastered_topics": mastered_topics,
            "learning_style": ["visual", "step-by-step", "retrieval practice"][index % 3],
            "grade_level": student["grade_level"],
            "profile_rating": student["profile_rating"],
            "average_session_rating": student["average_session_rating"],
            "study_streak_days": student["study_streak_days"],
            "preferred_language": student["preferred_language"],
            "purchased_note_ids": list(dict.fromkeys(purchases["notes"]))[:12],
            "purchased_book_ids": list(dict.fromkeys(purchases["books"]))[:12],
            "session_ids": session_ids_by_student.get(student["_id"], [])[:24],
            "ai_conversation_ids": [],
            "reflection_ids": [],
            "future_ai_instructions": [
                f"Start with a quick diagnostic on {weak_topics[0]}.",
                "Use the student's past tutor-session examples before introducing new rules.",
                "End with one short retrieval-practice question.",
            ],
            "successful_teaching_methods": ["worked examples", "quick check questions", "mistake correction"],
            "content_type": "student_profile",
            "seed_batch": BATCH_ID,
            "created_at": now,
            "updated_at": now,
        }
        profile["recommendation_vector"] = await vector_search.gemini.embed_text(
            " ".join([subject, *weak_topics, *mastered_topics, profile["learning_style"]])
        )
        profiles.append(profile)

    return profiles


def build_sessions(
    session_count: int,
    tutors: list[dict[str, Any]],
    students: list[dict[str, Any]],
    rng: random.Random,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    bookings: list[dict[str, Any]] = []
    sessions: list[dict[str, Any]] = []
    tutor_session_history: list[dict[str, Any]] = []
    transcripts: list[dict[str, Any]] = []
    reviews: list[dict[str, Any]] = []
    now = utc_now()

    for index in range(session_count):
        tutor = tutors[index % len(tutors)]
        student = students[(index * 11) % len(students)]
        subject = tutor["primary_subject"]
        area = next(area for area in SUBJECT_AREAS if area["subject"] == subject)
        topic = area["topics"][index % len(area["topics"])]
        duration = 30
        start = timestamp(2 + index % 365, 14 + index % 8, (index * 5) % 60)
        end = start + timedelta(minutes=duration)
        rating = round(4.0 + ((index * 13) % 100) / 100, 1)
        booking_id = f"bulk-booking-{index + 1:05d}"
        session_id = f"bulk-session-{index + 1:05d}"
        transcript = (
            f"Tutor: Today we worked on {topic} in {subject}. "
            f"Student: I got stuck when the problem changed wording. "
            f"Tutor: We used {tutor['teaching_style']} and practiced a worked example. "
            f"Student: The check question helped me explain {topic} back in my own words."
        )
        summary = (
            f"{student['name']} practiced {subject} topic {topic} with {tutor['display_name']}. "
            "The session used diagnostic questions, worked examples, and feedback on mistakes."
        )
        common_doc = {
            "booking_id": booking_id,
            "session_id": session_id,
            "tutor_id": tutor["_id"],
            "tutor_user_id": tutor["user_id"],
            "tutor_name": tutor["display_name"],
            "student_id": student["_id"],
            "student_user_id": student["_id"],
            "student_name": student["name"],
            "student_email": student["email"],
            "subject": subject,
            "topic": topic,
            "session_date": start.date().isoformat(),
            "start_time": start.isoformat(),
            "end_time": end.isoformat(),
            "started_at": start,
            "ended_at": end,
            "duration_minutes": duration,
            "rating": rating,
            "seed_batch": BATCH_ID,
            "created_at": now,
            "updated_at": now,
        }
        bookings.append(
            {
                "_id": booking_id,
                **{key: common_doc[key] for key in ["tutor_id", "student_id", "subject", "seed_batch", "created_at", "updated_at"]},
                "topic": topic,
                "starts_at": start,
                "ends_at": end,
                "duration_minutes": duration,
                "status": "completed",
                "room_id": f"bulk-room-{index + 1:05d}",
                "session_id": session_id,
            }
        )
        sessions.append(
            {
                "_id": session_id,
                **common_doc,
                "room_id": f"bulk-room-{index + 1:05d}",
                "status": "completed",
                "summary": summary,
                "student_questions": [
                    f"How do I recognize {topic} problems?",
                    f"What mistake should I check first for {subject}?",
                ],
                "weak_topics": [topic, f"{subject} problem setup"],
                "successful_teaching_methods": [tutor["teaching_style"], "quick check questions", "mistake correction"],
                "quiz_results": {"confidence_before": 2 + index % 3, "confidence_after": 3 + index % 3},
                "content_type": "lesson_summary",
            }
        )
        transcripts.append(
            {
                "_id": f"bulk-transcript-{index + 1:05d}",
                **common_doc,
                "transcript": transcript,
                "summary": summary,
                "content_type": "transcript",
            }
        )
        reviews.append(
            {
                "_id": f"bulk-review-{index + 1:05d}",
                "session_id": session_id,
                "tutor_id": tutor["_id"],
                "student_id": student["_id"],
                "subject": subject,
                "topic": topic,
                "rating": rating,
                "comment": f"Helpful session on {topic}; the tutor gave clear examples and practice steps.",
                "content_type": "review",
                "seed_batch": BATCH_ID,
                "created_at": now,
                "updated_at": now,
            }
        )
        tutor_session_history.append(
            {
                "_id": f"bulk-tutor-session-{index + 1:05d}",
                "session_id": session_id,
                "booking_id": booking_id,
                "tutor_id": tutor["_id"],
                "tutor_user_id": tutor["user_id"],
                "tutor_name": tutor["display_name"],
                "student_id": student["_id"],
                "student_name": student["name"],
                "subject": subject,
                "topic": topic,
                "session_date": start.date().isoformat(),
                "starts_at": start,
                "ends_at": end,
                "duration_minutes": 30,
                "rating": rating,
                "status": "completed",
                "student_questions": [
                    f"How do I recognize {topic} problems?",
                    f"What mistake should I check first for {subject}?",
                ],
                "summary": summary,
                "content_type": "tutor_session_history",
                "seed_batch": BATCH_ID,
                "created_at": now,
                "updated_at": now,
            }
        )

    return bookings, sessions, tutor_session_history, transcripts, reviews


async def build_dataset(args: argparse.Namespace, vector_search: VectorSearchService) -> dict[str, list[dict[str, Any]]]:
    rng = random.Random(args.seed)
    users, tutors, students = build_users_and_tutors(args.tutors, args.students, rng)
    books, book_chunks = build_books(args.books, rng)
    notes = build_notes(args.notes, tutors, rng)
    availability = build_availability(tutors, args.slots_per_tutor)
    bookings, sessions, tutor_session_history, transcripts, reviews = build_sessions(args.sessions, tutors, students, rng)
    purchases, purchase_history, purchased_by_student = build_purchases(args.purchases, students, notes, books, rng)
    student_profiles = await build_student_profiles(students, sessions, purchased_by_student, vector_search)

    dataset = {
        "users": users,
        "tutors": tutors,
        "student_learning_profiles": student_profiles,
        "books": books,
        "book_chunks": book_chunks,
        "notes": notes,
        "tutor_availability": availability,
        "bookings": bookings,
        "sessions": sessions,
        "tutor_session_history": tutor_session_history,
        "transcripts": transcripts,
        "reviews": reviews,
        "purchases": purchases,
        "purchase_history": purchase_history,
    }

    for collection in ["tutors", "books", "book_chunks", "notes", "sessions", "transcripts"]:
        await add_embeddings(vector_search, collection, dataset[collection])

    return dataset


async def main() -> None:
    parser = argparse.ArgumentParser(description="Insert a large TutorLoop demo dataset into MongoDB.")
    parser.add_argument("--tutors", type=int, default=DEFAULT_TUTOR_COUNT, help="Tutor users and profiles to create")
    parser.add_argument("--students", type=int, default=DEFAULT_STUDENT_COUNT, help="Student users used in session history")
    parser.add_argument("--sessions", type=int, default=DEFAULT_SESSION_COUNT, help="Past sessions to create")
    parser.add_argument("--books", type=int, default=DEFAULT_BOOK_COUNT, help="Books to create")
    parser.add_argument("--notes", type=int, default=DEFAULT_NOTE_COUNT, help="Notes to create")
    parser.add_argument("--purchases", type=int, default=DEFAULT_PURCHASE_COUNT, help="Past note/book purchases to create")
    parser.add_argument("--slots-per-tutor", type=int, default=DEFAULT_SLOTS_PER_TUTOR, help="Upcoming 30-minute availability slots per tutor")
    parser.add_argument("--seed", type=int, default=20260627, help="Deterministic random seed")
    parser.add_argument(
        "--timeout-ms",
        type=int,
        default=20000,
        help="MongoDB connection timeout in milliseconds",
    )
    parser.add_argument(
        "--keep-existing-batch",
        action="store_true",
        help="Do not delete previous records from this seed batch before insert",
    )
    args = parser.parse_args()

    settings = get_settings()
    if not settings.mongodb_uri:
        raise SystemExit("MONGODB_URI is required in .env to add the large dataset to MongoDB.")

    db = await connect_mongo(settings, timeout_ms=args.timeout_ms)
    if not db.is_mongo:
        message = db.connection_error or "unknown connection error"
        raise SystemExit(f"Could not connect to MongoDB: {message}")

    mock_embedding_settings = settings.model_copy(update={"gemini_api_key": None})
    gemini = GeminiService(mock_embedding_settings)
    vector_search = VectorSearchService(db, gemini, mock_embedding_settings)

    if not args.keep_existing_batch:
        for collection in BULK_COLLECTIONS:
            await db.delete_many(collection, {"seed_batch": BATCH_ID})

    dataset = await build_dataset(args, vector_search)
    inserted: dict[str, int] = {}
    for collection, docs in dataset.items():
        inserted[collection] = await insert_chunked(db, collection, docs)

    counts = {
        "tutor_users": await db.count_documents("users", {"role": "tutor", "seed_batch": BATCH_ID}),
        "tutor_profiles": await db.count_documents("tutors", {"seed_batch": BATCH_ID}),
        "student_users": await db.count_documents("users", {"role": "student", "seed_batch": BATCH_ID}),
        "student_profiles": await db.count_documents("student_learning_profiles", {"seed_batch": BATCH_ID}),
        "past_sessions": await db.count_documents("sessions", {"seed_batch": BATCH_ID}),
        "tutor_session_history": await db.count_documents("tutor_session_history", {"seed_batch": BATCH_ID}),
        "books": await db.count_documents("books", {"seed_batch": BATCH_ID}),
        "book_chunks": await db.count_documents("book_chunks", {"seed_batch": BATCH_ID}),
        "notes": await db.count_documents("notes", {"seed_batch": BATCH_ID}),
        "availability_slots": await db.count_documents("tutor_availability", {"seed_batch": BATCH_ID}),
        "purchases": await db.count_documents("purchases", {"seed_batch": BATCH_ID}),
        "purchase_history": await db.count_documents("purchase_history", {"seed_batch": BATCH_ID}),
        "reviews": await db.count_documents("reviews", {"seed_batch": BATCH_ID}),
    }

    await db.close()

    print("Inserted TutorLoop large demo batch into MongoDB.")
    print(f"Batch: {BATCH_ID}")
    print("Inserted collections:")
    for collection, count in inserted.items():
        print(f"  {collection}: {count}")
    print("Verified batch counts:")
    for name, count in counts.items():
        print(f"  {name}: {count}")


if __name__ == "__main__":
    asyncio.run(main())
