from __future__ import annotations

import asyncio
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from backend.app.core.config import get_settings
from backend.app.db.mongo import AppDatabase, utc_now
def _note_description(note: dict) -> str:
    subject = note.get("subject") or "this subject"
    title = note.get("title") or "this note"
    content = (note.get("content") or "").strip()
    preview = content[:180].rstrip()
    if preview and not preview.endswith("."):
        preview = f"{preview}..."
    lines = [
        f"This note explains {title} with a practical, student-friendly flow for {subject}.",
        "It breaks complex ideas into checkpoints you can review quickly before class or exams.",
        f"It includes worked examples and common pitfalls that appear in {subject} assignments.",
        f"Quick preview: {preview}" if preview else "Quick preview: concise concept summaries and guided practice prompts.",
    ]
    return "\n".join(lines)


def _book_description(book: dict) -> str:
    subject = book.get("subject") or "core subjects"
    title = book.get("title") or "this book"
    author = book.get("author") or "the TutorLoop team"
    lines = [
        f"{title} builds strong conceptual foundations for {subject} learners.",
        "Chapters progress from intuition to formal methods with worked examples.",
        "It is useful for tutoring follow-up, revision sessions, and deeper self-study.",
        f"Author/source: {author}.",
    ]
    return "\n".join(lines)


def _tutor_profile(tutor: dict) -> dict:
    name = tutor.get("display_name") or "This tutor"
    subjects = tutor.get("subjects") or []
    subject_text = ", ".join(subjects[:4]) if subjects else "core topics"
    headline_subject = subjects[0] if subjects else "general studies"
    return {
        "about_me": "\n".join(
            [
                f"I am {name}, and I specialize in helping students gain confidence in {headline_subject}.",
                "My sessions combine concept clarity, guided practice, and short understanding checks.",
                f"I support learners who want structured progress across {subject_text}.",
                "Students can expect patient explanations, practical examples, and a clear plan each week.",
            ]
        ),
        "major_topics": subjects[:6] if subjects else [headline_subject],
        "credentials": "\n".join(
            [
                "Academic background aligned to tutoring subjects and curriculum standards.",
                "Experience delivering one-to-one and small-group tutoring sessions.",
                "Track record of helping students improve confidence and exam performance.",
            ]
        ),
        "study_experience": f"Formal study in {headline_subject} and related disciplines.",
        "work_experience": "Tutoring experience across school and university-level coursework.",
    }


async def main() -> None:
    settings = get_settings()
    db = AppDatabase(settings)
    await db.connect()
    if not db.is_mongo:
        raise SystemExit("MONGODB_URI is required to enrich existing MongoDB data.")

    notes = await db.find_many("notes", {}, limit=5000)
    books = await db.find_many("books", {}, limit=5000)
    tutors = await db.find_many("tutors", {}, limit=5000)

    note_updates = 0
    for note in notes:
        description = _note_description(note)
        await db.update_one(
            "notes",
            {"_id": note["_id"]},
            {"$set": {"description": description, "updated_at": utc_now()}},
        )
        note_updates += 1

    book_updates = 0
    for book in books:
        description = _book_description(book)
        await db.update_one(
            "books",
            {"_id": book["_id"]},
            {"$set": {"description": description, "updated_at": utc_now()}},
        )
        book_updates += 1

    tutor_updates = 0
    for tutor in tutors:
        profile = _tutor_profile(tutor)
        await db.update_one(
            "tutors",
            {"_id": tutor["_id"]},
            {"$set": {**profile, "updated_at": utc_now()}},
        )
        tutor_updates += 1

    await db.close()
    print(f"Updated notes: {note_updates}")
    print(f"Updated books: {book_updates}")
    print(f"Updated tutors: {tutor_updates}")


if __name__ == "__main__":
    asyncio.run(main())
