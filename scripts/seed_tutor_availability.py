from __future__ import annotations

import asyncio
import hashlib
import sys
from datetime import timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.app.core.config import get_settings
from backend.app.db.mongo import AppDatabase, utc_now


def score(*parts: str) -> int:
    text = "|".join(parts).encode("utf-8")
    return int(hashlib.sha256(text).hexdigest()[:8], 16) % 100


async def main() -> None:
    settings = get_settings()
    db = AppDatabase(settings)
    await db.connect()
    if not db.is_mongo:
        raise RuntimeError("This script is intended for MongoDB mode only.")

    tutors = await db.find_many("tutors", {}, limit=10000)
    if not tutors:
        print("No tutors found.")
        await db.close()
        return

    now = utc_now().replace(minute=0, second=0, microsecond=0)
    start = now
    end = now + timedelta(days=15)

    # Clear only the target 15-day window.
    await db.delete_many(
        "tutor_availability",
        {
            "starts_at": {"$gte": start, "$lte": end},
        },
    )

    docs: list[dict] = []
    for tutor in tutors:
        tutor_id = tutor["_id"]
        tutor_name = tutor.get("display_name", tutor_id)
        subject = (tutor.get("subjects") or ["General"])[0]
        for day_offset in range(15):
            day = (start + timedelta(days=day_offset)).replace(hour=0, minute=0, second=0, microsecond=0)
            for slot_index in range(48):  # every half-hour in a day
                starts_at = day + timedelta(minutes=30 * slot_index)
                ends_at = starts_at + timedelta(minutes=30)
                hour = starts_at.hour

                # Working window: 08:00-20:00 has possible availability.
                in_working_hours = 8 <= hour < 20
                availability_score = score(tutor_id, starts_at.isoformat())
                status = "available" if (in_working_hours and availability_score < 55) else "blocked"

                docs.append(
                    {
                        "tutor_id": tutor_id,
                        "tutor_name": tutor_name,
                        "subject": subject,
                        "topic": f"{subject} tutoring slot",
                        "starts_at": starts_at,
                        "ends_at": ends_at,
                        "duration_minutes": 30,
                        "status": status,
                        "timezone": "UTC",
                        "slot_type": "live_tutoring",
                        "content_type": "tutor_availability",
                        "seed_batch": "availability-v2",
                        "created_at": now,
                        "updated_at": now,
                    }
                )

    batch_size = 5000
    coll = db.collection("tutor_availability")
    for i in range(0, len(docs), batch_size):
        await coll.insert_many(docs[i : i + batch_size], ordered=False)

    available_count = await db.count_documents(
        "tutor_availability",
        {"starts_at": {"$gte": start, "$lte": end}, "status": "available"},
    )
    blocked_count = await db.count_documents(
        "tutor_availability",
        {"starts_at": {"$gte": start, "$lte": end}, "status": "blocked"},
    )
    total = available_count + blocked_count
    print(
        f"Seeded {total} slots for {len(tutors)} tutors "
        f"(available={available_count}, blocked={blocked_count})"
    )
    await db.close()


if __name__ == "__main__":
    asyncio.run(main())
