from __future__ import annotations

import asyncio
import sys
from pathlib import Path

from motor.motor_asyncio import AsyncIOMotorClient

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from backend.app.core.config import get_settings
from backend.app.services.vector_search import (
    filters_for_collection,
    index_for_collection,
)


VECTOR_COLLECTIONS = [
    "notes",
    "tutors",
    "transcripts",
    "ai_reflections",
    "books",
    "book_chunks",
    "ai_conversations",
]


def definition_for(collection: str, dimensions: int) -> dict:
    """Build a distinct index definition per collection.

    Each collection only declares the filter fields it actually uses, so the
    indexes are genuinely distinct rather than one shared definition.
    """
    fields = [
        {
            "type": "vector",
            "path": "embedding",
            "numDimensions": dimensions,
            "similarity": "cosine",
        }
    ]
    fields.extend({"type": "filter", "path": path} for path in filters_for_collection(collection))
    return {"fields": fields}


async def upsert_vector_index(db, collection: str, index_name: str, definition: dict) -> str:
    existing = await db.command(
        {
            "listSearchIndexes": collection,
            "name": index_name,
        }
    )
    existing_batch = existing.get("cursor", {}).get("firstBatch", [])
    if existing_batch:
        await db.command(
            {
                "updateSearchIndex": collection,
                "name": index_name,
                "definition": definition,
            }
        )
        return "updated"

    await db.command(
        {
            "createSearchIndexes": collection,
            "indexes": [
                {
                    "name": index_name,
                    "type": "vectorSearch",
                    "definition": definition,
                }
            ],
        }
    )
    return "created"


async def main() -> None:
    settings = get_settings()
    if not settings.mongodb_uri:
        raise SystemExit("MONGODB_URI is not set.")

    client = AsyncIOMotorClient(
        settings.mongodb_uri,
        serverSelectionTimeoutMS=settings.mongodb_timeout_ms,
        connectTimeoutMS=settings.mongodb_timeout_ms,
        socketTimeoutMS=settings.mongodb_timeout_ms,
    )
    db = client[settings.mongodb_db_name]

    print(f"Database: {settings.mongodb_db_name}")
    for collection in VECTOR_COLLECTIONS:
        index_name = index_for_collection(collection, settings.mongodb_vector_index)
        definition = definition_for(collection, settings.embedding_dimensions)
        action = await upsert_vector_index(db, collection, index_name, definition)
        filter_paths = ", ".join(field["path"] for field in definition["fields"] if field["type"] == "filter")
        print(f"{collection}: {action} (index='{index_name}', filters=[{filter_paths}])")

    await db["users"].create_index([("email", 1)], unique=True)
    await db["bookings"].create_index([("student_id", 1), ("starts_at", -1)])
    await db["bookings"].create_index([("tutor_id", 1), ("starts_at", -1)])
    await db["ai_conversations"].create_index([("student_id", 1), ("created_at", -1)])
    await db["recommendations"].create_index([("student_id", 1), ("score", -1)])
    print("Standard indexes ensured.")
    client.close()


if __name__ == "__main__":
    asyncio.run(main())
