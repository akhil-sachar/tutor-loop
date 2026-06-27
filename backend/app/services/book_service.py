from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from backend.app.db.mongo import utc_now


CONTENT_DIR = Path(__file__).resolve().parent.parent / "content"
CHUNK_SIZE = 1400
CHUNK_OVERLAP = 200
MAX_PAGES_PER_BOOK = 80

BOOK_CATALOG: list[dict[str, Any]] = [
    {
        "_id": "book-mit-calculus",
        "title": "MIT RES 18.001 Calculus",
        "subject": "Calculus",
        "description": "MIT OpenCourseWare calculus textbook covering limits, derivatives, integrals, and applications.",
        "filename": "mitres_18_001_f17_full_book.pdf",
        "price": 0.0,
        "rating": 4.9,
        "author": "MIT OpenCourseWare",
        "content_type": "book",
    },
    {
        "_id": "book-mml",
        "title": "Mathematics for Machine Learning",
        "subject": "Linear Algebra",
        "description": "Vectors, matrices, eigenvalues, and calculus foundations for machine learning.",
        "filename": "mml-book.pdf",
        "price": 0.0,
        "rating": 4.8,
        "author": "Deisenroth, Faisal, Ong",
        "content_type": "book",
    },
    {
        "_id": "book-linear-guest",
        "title": "Linear Algebra Guest Lecture Notes",
        "subject": "Linear Algebra",
        "description": "Introductory linear algebra notes on vectors, spans, and matrix operations.",
        "filename": "linear-guest.pdf",
        "price": 0.0,
        "rating": 4.6,
        "author": "Guest lecture series",
        "content_type": "book",
    },
    {
        "_id": "book-transformer-survey",
        "title": "Transformer Architecture Survey",
        "subject": "Machine Learning",
        "description": "Survey of transformer models, attention, and modern deep learning architectures.",
        "filename": "2501.09223v2.pdf",
        "price": 0.0,
        "rating": 4.7,
        "author": "Research survey",
        "content_type": "book",
    },
    {
        "_id": "book-springer-ml",
        "title": "Machine Learning Foundations",
        "subject": "Machine Learning",
        "description": "Foundational machine learning concepts from a Springer reference text.",
        "filename": "978-3-031-54827-7.pdf",
        "price": 0.0,
        "rating": 4.5,
        "author": "Springer",
        "content_type": "book",
    },
]


class BookService:
    def __init__(self, db: Any, vector_search: Any):
        self.db = db
        self.vector_search = vector_search

    async def ensure_books_ingested(self) -> dict[str, Any]:
        if await self.db.find_one("books", {"_id": BOOK_CATALOG[0]["_id"]}):
            chunk_docs = await self.db.find_many("book_chunks", {}, limit=5000)
            return {"ingested": False, "books": len(BOOK_CATALOG), "chunks": len(chunk_docs)}

        await self.db.delete_many("books", {})
        await self.db.delete_many("book_chunks", {})

        books_created = 0
        chunks_created = 0
        for book in BOOK_CATALOG:
            pdf_path = CONTENT_DIR / book["filename"]
            if not pdf_path.exists():
                continue

            book_doc = {**book, "source_path": str(pdf_path.name), "created_at": utc_now()}
            book_doc["embedding"] = await self.vector_search.embed_document(
                book_doc,
                ["title", "subject", "description", "author"],
            )
            await self.db.insert_one("books", book_doc)
            books_created += 1

            text = self._extract_pdf_text(pdf_path)
            chunks = self._chunk_text(text)
            for index, chunk in enumerate(chunks):
                chunk_doc = {
                    "book_id": book["_id"],
                    "title": book["title"],
                    "subject": book["subject"],
                    "chunk_index": index,
                    "content": chunk,
                    "content_type": "book_chunk",
                }
                chunk_doc["embedding"] = await self.vector_search.embed_document(
                    chunk_doc,
                    ["title", "subject", "content"],
                )
                await self.db.insert_one("book_chunks", chunk_doc)
                chunks_created += 1

        return {"ingested": True, "books": books_created, "chunks": chunks_created}

    def _extract_pdf_text(self, pdf_path: Path) -> str:
        try:
            from pypdf import PdfReader
        except ImportError:
            return self._fallback_text(pdf_path.stem)

        reader = PdfReader(str(pdf_path))
        pages: list[str] = []
        for page in reader.pages[:MAX_PAGES_PER_BOOK]:
            text = page.extract_text() or ""
            cleaned = re.sub(r"\s+", " ", text).strip()
            if cleaned:
                pages.append(cleaned)
        if pages:
            return "\n\n".join(pages)
        return self._fallback_text(pdf_path.stem)

    def _fallback_text(self, stem: str) -> str:
        lower = stem.lower()
        if "calculus" in lower or "18_001" in lower:
            return (
                "A derivative measures the instantaneous rate of change of a function. "
                "The limit definition uses secant slopes approaching a tangent slope. "
                "Power rule, product rule, and chain rule build on this intuition."
            )
        if "mml" in lower or "linear" in lower:
            return (
                "Linear algebra studies vectors, matrices, and linear transformations. "
                "Eigenvalues and eigenvectors describe how transformations stretch space."
            )
        if "2501" in lower or "transformer" in lower:
            return (
                "Transformers use self-attention to relate tokens in a sequence. "
                "Multi-head attention and positional encodings are core building blocks."
            )
        return f"Reference material from {stem.replace('-', ' ')} for TutorLoop tutoring."

    def _chunk_text(self, text: str) -> list[str]:
        normalized = re.sub(r"\s+", " ", text).strip()
        if not normalized:
            return []
        if len(normalized) <= CHUNK_SIZE:
            return [normalized]

        chunks: list[str] = []
        start = 0
        while start < len(normalized):
            end = min(start + CHUNK_SIZE, len(normalized))
            if end < len(normalized):
                split_at = normalized.rfind(" ", start + CHUNK_SIZE // 2, end)
                if split_at > start:
                    end = split_at
            chunk = normalized[start:end].strip()
            if chunk:
                chunks.append(chunk)
            if end >= len(normalized):
                break
            start = max(end - CHUNK_OVERLAP, start + 1)
        return chunks
