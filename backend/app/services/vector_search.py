from __future__ import annotations

import math
import re
from typing import Any

from backend.app.db.mongo import matches_filter


COLLECTION_TITLES = {
    "notes": "title",
    "books": "title",
    "book_chunks": "title",
    "tutors": "display_name",
    "sessions": "subject",
    "transcripts": "subject",
    "ai_reflections": "subject",
    "ai_conversations": "subject",
}


class VectorSearchService:
    """MongoDB Atlas Vector Search with local fallback scoring."""

    def __init__(self, db: Any, gemini: Any, settings: Any):
        self.db = db
        self.gemini = gemini
        self.settings = settings

    async def embed_document(self, doc: dict[str, Any], fields: list[str]) -> list[float]:
        text = " ".join(str(doc.get(field, "")) for field in fields)
        return await self.gemini.embed_text(text)

    async def search(
        self,
        *,
        query: str,
        collections: list[str],
        filters: dict[str, Any] | None = None,
        limit: int = 8,
    ) -> list[dict[str, Any]]:
        embedding = await self.gemini.embed_text(query)
        all_results: list[dict[str, Any]] = []
        filters = filters or {}

        for collection in collections:
            collection_filter = self._filter_for_collection(collection, filters)
            if self.db.is_mongo:
                try:
                    results = await self._atlas_vector_search(collection, embedding, collection_filter, limit)
                except Exception:
                    results = await self._local_vector_search(collection, query, embedding, collection_filter, limit)
            else:
                results = await self._local_vector_search(collection, query, embedding, collection_filter, limit)
            all_results.extend(results)

        all_results.sort(key=lambda item: item["score"], reverse=True)
        return all_results[:limit]

    async def _atlas_vector_search(
        self,
        collection: str,
        embedding: list[float],
        filters: dict[str, Any],
        limit: int,
    ) -> list[dict[str, Any]]:
        # Sponsor integration: MongoDB Atlas Vector Search performs semantic
        # retrieval over notes, tutors, lesson summaries, and AI reflections.
        vector_stage: dict[str, Any] = {
            "index": self.settings.mongodb_vector_index,
            "path": "embedding",
            "queryVector": embedding,
            "numCandidates": 100,
            "limit": limit,
        }
        if filters:
            vector_stage["filter"] = filters

        pipeline = [
            {"$vectorSearch": vector_stage},
            {"$addFields": {"score": {"$meta": "vectorSearchScore"}}},
            {"$limit": limit},
        ]
        docs = await self.db.collection(collection).aggregate(pipeline).to_list(length=limit)
        return [self._shape_result(collection, doc, doc.get("score", 0.0)) for doc in docs]

    async def _local_vector_search(
        self,
        collection: str,
        query: str,
        embedding: list[float],
        filters: dict[str, Any],
        limit: int,
    ) -> list[dict[str, Any]]:
        docs = await self.db.find_many(collection, filters, limit=200)
        results = []
        for doc in docs:
            vector_score = self._cosine(embedding, doc.get("embedding") or [])
            lexical_score = self._lexical_score(query, self._text_for_doc(doc))
            rating_boost = min(float(doc.get("rating", 0)) / 5.0, 1.0) * 0.08
            score = (0.65 * vector_score) + (0.35 * lexical_score) + rating_boost
            results.append(self._shape_result(collection, doc, score))
        results.sort(key=lambda item: item["score"], reverse=True)
        return results[:limit]

    def _filter_for_collection(self, collection: str, filters: dict[str, Any]) -> dict[str, Any]:
        query: dict[str, Any] = {}
        subject = filters.get("subject")
        if subject:
            query["subjects" if collection == "tutors" else "subject"] = subject
        if collection == "notes":
            if filters.get("max_price") is not None:
                query["price"] = {"$lte": float(filters["max_price"])}
            if filters.get("min_rating") is not None:
                query["rating"] = {"$gte": float(filters["min_rating"])}
        if collection == "tutors":
            if filters.get("max_rate") is not None:
                query["hourly_rate"] = {"$lte": float(filters["max_rate"])}
            if filters.get("min_rating") is not None:
                query["rating"] = {"$gte": float(filters["min_rating"])}
        content_type = filters.get("content_type")
        if content_type:
            query["content_type"] = content_type
        return query

    def _shape_result(self, collection: str, doc: dict[str, Any], score: float) -> dict[str, Any]:
        title_field = COLLECTION_TITLES.get(collection, "title")
        title = str(doc.get(title_field) or doc.get("title") or doc.get("subject") or collection)
        return {
            **doc,
            "id": str(doc.get("_id")),
            "collection": collection,
            "content_type": doc.get("content_type", collection.rstrip("s")),
            "title": title,
            "score": round(float(score), 4),
            "snippet": self._snippet(doc),
        }

    def _text_for_doc(self, doc: dict[str, Any]) -> str:
        keys = [
            "title",
            "subject",
            "description",
            "content",
            "bio",
            "teaching_style",
            "summary",
            "transcript",
            "question",
            "answer",
        ]
        return " ".join(str(doc.get(key, "")) for key in keys)

    def _snippet(self, doc: dict[str, Any]) -> str:
        text = self._text_for_doc(doc).strip()
        return re.sub(r"\s+", " ", text)[:260]

    def _cosine(self, left: list[float], right: list[float]) -> float:
        if not left or not right:
            return 0.0
        length = min(len(left), len(right))
        dot = sum(left[index] * right[index] for index in range(length))
        left_mag = math.sqrt(sum(value * value for value in left[:length])) or 1.0
        right_mag = math.sqrt(sum(value * value for value in right[:length])) or 1.0
        return max(0.0, dot / (left_mag * right_mag))

    def _lexical_score(self, query: str, text: str) -> float:
        query_terms = {term for term in re.findall(r"[a-z0-9]+", query.lower()) if len(term) > 2}
        if not query_terms:
            return 0.0
        text_lower = text.lower()
        matches = sum(1 for term in query_terms if term in text_lower)
        return min(matches / len(query_terms), 1.0)
