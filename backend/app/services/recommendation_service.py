from __future__ import annotations

from typing import Any

from backend.app.db.mongo import utc_now


class RecommendationService:
    def __init__(self, db: Any, vector_search: Any, gemini: Any):
        self.db = db
        self.vector_search = vector_search
        self.gemini = gemini

    async def refresh_for_student(self, student_id: str) -> list[dict[str, Any]]:
        profile = await self.db.find_one("student_learning_profiles", {"student_id": student_id})
        if not profile:
            profile = await self._create_default_profile(student_id)

        weak_topics = profile.get("weak_topics", []) or ["calculus foundations"]
        query = " ".join(weak_topics + profile.get("mastered_topics", []))
        purchased = set(profile.get("purchased_note_ids", []))

        note_matches = await self.vector_search.search(query=query, collections=["notes"], limit=8)
        book_matches = await self.vector_search.search(query=query, collections=["books"], limit=4)
        tutor_matches = await self.vector_search.search(query=query, collections=["tutors"], limit=6)

        recommendations: list[dict[str, Any]] = []
        for match in note_matches:
            if match.get("_id") in purchased:
                continue
            recommendations.append(
                {
                    "student_id": student_id,
                    "type": "note",
                    "target_id": match["_id"],
                    "title": match["title"],
                    "subject": match.get("subject"),
                    "reason": f"Matches weak topic memory: {', '.join(weak_topics[:3])}.",
                    "score": round(match["score"] + self._price_boost(match), 4),
                    "metadata": {"price": match.get("price"), "rating": match.get("rating")},
                    "created_at": utc_now(),
                }
            )

        purchased_books = set(profile.get("purchased_book_ids", []))
        for match in book_matches:
            if match.get("_id") in purchased_books:
                continue
            recommendations.append(
                {
                    "student_id": student_id,
                    "type": "book",
                    "target_id": match["_id"],
                    "title": match["title"],
                    "subject": match.get("subject"),
                    "reason": f"Platform book aligned with weak topics: {', '.join(weak_topics[:3])}.",
                    "score": round(match["score"] + 0.05, 4),
                    "metadata": {"price": match.get("price", 0), "rating": match.get("rating")},
                    "created_at": utc_now(),
                }
            )

        for match in tutor_matches:
            recommendations.append(
                {
                    "student_id": student_id,
                    "type": "tutor",
                    "target_id": match["_id"],
                    "title": match["display_name"],
                    "subject": ", ".join(match.get("subjects", [])[:3]),
                    "reason": f"Teaching style aligns with profile: {match.get('teaching_style', '')[:120]}",
                    "score": round(match["score"] + float(match.get("rating", 0)) / 10, 4),
                    "metadata": {"hourly_rate": match.get("hourly_rate"), "rating": match.get("rating")},
                    "created_at": utc_now(),
                }
            )

        for topic in weak_topics[:3]:
            recommendations.append(
                {
                    "student_id": student_id,
                    "type": "ai_lesson",
                    "target_id": f"ai-lesson-{topic.lower().replace(' ', '-')}",
                    "title": f"AI lesson: {topic}",
                    "subject": profile.get("primary_subject", "Math"),
                    "reason": "Generated from continual-learning reflections and quiz results.",
                    "score": 0.9,
                    "metadata": {"source": "student_learning_profile"},
                    "created_at": utc_now(),
                }
            )

        recommendations.sort(key=lambda item: item["score"], reverse=True)
        recommendations = recommendations[:10]
        await self.db.delete_many("recommendations", {"student_id": student_id})
        for item in recommendations:
            await self.db.insert_one("recommendations", item)
        return await self.get_for_student(student_id)

    async def get_for_student(self, student_id: str) -> list[dict[str, Any]]:
        existing = await self.db.find_many(
            "recommendations",
            {"student_id": student_id},
            sort=[("score", -1)],
            limit=20,
        )
        if existing:
            return existing
        return await self.refresh_for_student(student_id)

    async def _create_default_profile(self, student_id: str) -> dict[str, Any]:
        profile = {
            "_id": student_id,
            "student_id": student_id,
            "primary_subject": "Math",
            "weak_topics": ["derivatives as instant rate of change"],
            "mastered_topics": [],
            "learning_style": "visual, step-by-step",
            "purchased_note_ids": [],
            "session_ids": [],
            "reflection_ids": [],
            "future_ai_instructions": [],
            "recommendation_vector": await self.gemini.embed_text("derivatives visual step-by-step calculus"),
            "content_type": "student_profile",
            "created_at": utc_now(),
            "updated_at": utc_now(),
        }
        await self.db.insert_one("student_learning_profiles", profile)
        return profile

    def _price_boost(self, note: dict[str, Any]) -> float:
        price = float(note.get("price") or 0)
        return max(0, 0.12 - (price / 100))
