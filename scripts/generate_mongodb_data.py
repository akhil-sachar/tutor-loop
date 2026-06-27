from __future__ import annotations

import argparse
import asyncio
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from backend.app.core.config import get_settings
from backend.app.db.mongo import AppDatabase, utc_now
from backend.app.seed import DEMO_STUDENT_ID, DEMO_TUTOR_ID, seed_demo_data
from backend.app.services.book_service import BookService
from backend.app.services.gemini_service import GeminiService
from backend.app.services.recommendation_service import RecommendationService
from backend.app.services.reflection_service import ReflectionService
from backend.app.services.vector_search import VectorSearchService


DEFAULT_OUTPUT = ROOT_DIR / "scripts" / "mongodb_data"

COLLECTIONS = [
    "users",
    "tutors",
    "notes",
    "books",
    "book_chunks",
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


def serialize_value(value: Any) -> Any:
    if isinstance(value, datetime):
        return {"$date": value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")}
    if isinstance(value, list):
        return [serialize_value(item) for item in value]
    if isinstance(value, dict):
        return {key: serialize_value(item) for key, item in value.items()}
    return value


def serialize_doc(doc: dict[str, Any]) -> dict[str, Any]:
    return serialize_value(doc)


async def enrich_demo_data(db: Any, gemini: Any, vector_search: Any, recommendations: Any, reflections: Any) -> None:
    """Add purchases, reviews, reflections, and AI session memory for a richer Atlas upload."""
    await db.insert_one(
        "purchases",
        {
            "_id": "purchase-demo-derivatives",
            "note_id": "note-derivatives-visual",
            "student_id": DEMO_STUDENT_ID,
            "amount": 9.0,
            "status": "simulated_paid",
            "content_type": "purchase",
        },
    )
    await db.update_one(
        "notes",
        {"_id": "note-derivatives-visual"},
        {"$inc": {"purchases_count": 1}},
    )
    await db.update_one(
        "student_learning_profiles",
        {"student_id": DEMO_STUDENT_ID},
        {
            "$addToSet": {
                "purchased_note_ids": "note-derivatives-visual",
                "purchased_book_ids": "book-mit-calculus",
            }
        },
    )

    await db.insert_many(
        "reviews",
        [
            {
                "_id": "review-elena-derivatives",
                "tutor_id": DEMO_TUTOR_ID,
                "student_id": DEMO_STUDENT_ID,
                "subject": "Calculus",
                "rating": 5,
                "comment": "The graph-first derivative explanation finally clicked for me.",
                "content_type": "review",
            },
            {
                "_id": "review-note-visual",
                "note_id": "note-derivatives-visual",
                "student_id": DEMO_STUDENT_ID,
                "rating": 5,
                "comment": "Short, visual, and exactly what I needed before my tutoring session.",
                "content_type": "review",
            },
        ],
    )

    await reflections.reflect_session(
        session_id="session-demo-derivatives",
        transcript=None,
        target_language="English",
    )

    conversation = {
        "_id": "ai-conversation-demo-derivatives",
        "student_id": DEMO_STUDENT_ID,
        "question": "Can you explain derivatives using what my tutor just taught me?",
        "answer": (
            "Your tutor emphasized secant slopes becoming a tangent slope. "
            "That is the limit definition of the derivative: the instant rate of change at one point."
        ),
        "subject": "Calculus",
        "language": "English",
        "status": "completed",
        "content_type": "ai_conversation",
        "created_at": utc_now(),
    }
    conversation["embedding"] = await vector_search.embed_document(
        conversation,
        ["subject", "question", "answer"],
    )
    await db.insert_one("ai_conversations", conversation)
    await reflections.reflect_ai_conversation(
        conversation_id=conversation["_id"],
        target_language="Spanish",
    )
    await recommendations.refresh_for_student(DEMO_STUDENT_ID)


async def build_dataset(*, chunks_per_book: int | None) -> AppDatabase:
    settings = get_settings().model_copy(update={"mongodb_uri": None})
    db = AppDatabase(settings)
    await db.connect()

    gemini = GeminiService(settings)
    vector_search = VectorSearchService(db, gemini, settings)
    recommendations = RecommendationService(db, vector_search, gemini)
    reflections = ReflectionService(db, gemini, vector_search, recommendations)
    books = BookService(db, vector_search)

    await seed_demo_data(db, gemini, vector_search, reset=True)
    await books.ensure_books_ingested()

    if chunks_per_book is not None:
        all_chunks = await db.find_many("book_chunks", {}, limit=10000)
        keep_chunks: list[dict[str, Any]] = []
        per_book: dict[str, int] = {}
        for chunk in sorted(all_chunks, key=lambda item: (item.get("book_id", ""), item.get("chunk_index", 0))):
            book_id = chunk.get("book_id", "")
            if per_book.get(book_id, 0) >= chunks_per_book:
                continue
            keep_chunks.append(chunk)
            per_book[book_id] = per_book.get(book_id, 0) + 1
        if db.is_mongo:
            await db.delete_many("book_chunks", {})
            for chunk in keep_chunks:
                await db.insert_one("book_chunks", chunk)
        else:
            db.memory["book_chunks"] = keep_chunks

    await enrich_demo_data(db, gemini, vector_search, recommendations, reflections)
    return db


async def export_collections(db: AppDatabase, output_dir: Path) -> dict[str, Any]:
    output_dir.mkdir(parents=True, exist_ok=True)
    manifest: dict[str, Any] = {
        "database": "tutorloop",
        "generated_at": utc_now().isoformat(),
        "collections": {},
    }

    for collection in COLLECTIONS:
        docs = await db.find_many(collection, {}, limit=10000)
        serialized = [serialize_doc(doc) for doc in docs]
        path = output_dir / f"{collection}.json"
        path.write_text(json.dumps(serialized, indent=2), encoding="utf-8")
        manifest["collections"][collection] = {"file": path.name, "count": len(serialized)}

    (output_dir / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return manifest


def deserialize_value(value: Any) -> Any:
    if isinstance(value, dict) and "$date" in value:
        raw = value["$date"]
        if raw.endswith("Z"):
            raw = raw.replace("Z", "+00:00")
        return datetime.fromisoformat(raw)
    if isinstance(value, list):
        return [deserialize_value(item) for item in value]
    if isinstance(value, dict):
        return {key: deserialize_value(item) for key, item in value.items()}
    return value


async def upload_collections(settings: Any, output_dir: Path, *, reset: bool) -> dict[str, Any]:
    if not settings.mongodb_uri:
        raise RuntimeError("MONGODB_URI is required for upload")

    db = AppDatabase(settings)
    await db.connect()
    if not db.is_mongo:
        raise RuntimeError("Could not connect to MongoDB with MONGODB_URI")

    uploaded: dict[str, int] = {}
    if reset:
        for collection in COLLECTIONS:
            await db.delete_many(collection, {})

    for collection in COLLECTIONS:
        path = output_dir / f"{collection}.json"
        if not path.exists():
            continue
        docs = json.loads(path.read_text(encoding="utf-8"))
        docs = [deserialize_value(doc) for doc in docs]
        if docs:
            await db.insert_many(collection, docs)
        uploaded[collection] = len(docs)

    await db.close()
    return uploaded


async def main() -> None:
    parser = argparse.ArgumentParser(description="Generate TutorLoop MongoDB upload data.")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT, help="Directory for JSON export files")
    parser.add_argument(
        "--chunks-per-book",
        type=int,
        default=12,
        help="Limit exported book chunks per title (use 0 for all chunks)",
    )
    parser.add_argument("--full-books", action="store_true", help="Export every ingested book chunk")
    parser.add_argument("--upload", action="store_true", help="Upload generated JSON to MONGODB_URI")
    parser.add_argument("--reset", action="store_true", help="Drop existing collections before upload")
    args = parser.parse_args()

    chunk_limit = None if args.full_books or args.chunks_per_book == 0 else args.chunks_per_book
    db = await build_dataset(chunks_per_book=chunk_limit)
    manifest = await export_collections(db, args.output)
    await db.close()

    print(f"Exported TutorLoop data to {args.output}")
    for name, info in manifest["collections"].items():
        print(f"  {name}: {info['count']} documents")

    if args.upload:
        get_settings.cache_clear()
        settings = get_settings()
        if not settings.mongodb_uri:
            raise SystemExit("Set MONGODB_URI in .env before using --upload")
        uploaded = await upload_collections(settings, args.output, reset=args.reset)
        print(f"Uploaded to database: {settings.mongodb_db_name}")
        print("Uploaded collections:")
        for name, count in uploaded.items():
            print(f"  {name}: {count} documents")


if __name__ == "__main__":
    asyncio.run(main())
