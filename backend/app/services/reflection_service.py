from __future__ import annotations

from typing import Any

from backend.app.db.mongo import utc_now


class ReflectionService:
    def __init__(self, db: Any, gemini: Any, vector_search: Any, recommendations: Any):
        self.db = db
        self.gemini = gemini
        self.vector_search = vector_search
        self.recommendations = recommendations

    async def reflect_session(
        self,
        *,
        session_id: str,
        transcript: str | None,
        target_language: str,
    ) -> dict[str, Any]:
        session = await self.db.find_one("sessions", {"_id": session_id})
        if not session:
            raise ValueError("Session not found")

        transcript_text = transcript or self._mock_transcript(session)
        transcript_doc = {
            "session_id": session_id,
            "student_id": session["student_id"],
            "tutor_id": session["tutor_id"],
            "subject": session["subject"],
            "transcript": transcript_text,
            "language": "English",
            "source": "mock" if transcript is None else "uploaded",
            "content_type": "transcript",
        }
        transcript_doc["embedding"] = await self.vector_search.embed_document(
            transcript_doc,
            ["subject", "transcript"],
        )
        transcript_id = await self.db.insert_one("transcripts", transcript_doc)

        reflection, is_mock = await self.gemini.reflect_session(
            transcript=transcript_text,
            subject=session["subject"],
            target_language=target_language,
        )

        reflection_doc = {
            "session_id": session_id,
            "transcript_id": transcript_id,
            "student_id": session["student_id"],
            "tutor_id": session["tutor_id"],
            "subject": session["subject"],
            "summary": reflection["summary"],
            "translated_summary": reflection["translated_summary"],
            "weaknesses": reflection["weaknesses"],
            "successful_teaching_methods": reflection["successful_teaching_methods"],
            "future_ai_instructions": reflection["future_ai_instructions"],
            "quiz_results": reflection["quiz_results"],
            "recommendation_text": reflection["recommendation_text"],
            "content_type": "ai_reflection",
            "created_at": utc_now(),
        }
        reflection_doc["embedding"] = await self.vector_search.embed_document(
            reflection_doc,
            ["subject", "summary", "recommendation_text"],
        )
        reflection_id = await self.db.insert_one("ai_reflections", reflection_doc)

        updated_profile = await self._update_student_profile(
            student_id=session["student_id"],
            session_id=session_id,
            reflection_id=reflection_id,
            reflection=reflection_doc,
        )
        await self.db.update_one(
            "sessions",
            {"_id": session_id},
            {"$set": {"status": "reflected", "transcript_id": transcript_id, "reflection_id": reflection_id}},
        )
        await self.db.update_one(
            "bookings",
            {"_id": session["booking_id"]},
            {"$set": {"status": "reflected"}},
        )
        await self.recommendations.refresh_for_student(session["student_id"])

        return {
            "reflection_id": reflection_id,
            "session_id": session_id,
            "student_id": session["student_id"],
            "summary": reflection_doc["summary"],
            "translated_summary": reflection_doc["translated_summary"],
            "weaknesses": reflection_doc["weaknesses"],
            "successful_teaching_methods": reflection_doc["successful_teaching_methods"],
            "future_ai_instructions": reflection_doc["future_ai_instructions"],
            "updated_profile": updated_profile,
            "is_mock": is_mock,
        }

    async def _update_student_profile(
        self,
        *,
        student_id: str,
        session_id: str,
        reflection_id: str,
        reflection: dict[str, Any],
    ) -> dict[str, Any]:
        profile = await self.db.find_one("student_learning_profiles", {"student_id": student_id})
        existing_text = " ".join((profile or {}).get("weak_topics", []))
        vector_text = " ".join(
            [
                existing_text,
                " ".join(reflection.get("weaknesses", [])),
                " ".join(reflection.get("future_ai_instructions", [])),
                reflection.get("summary", ""),
            ]
        )
        recommendation_vector = await self.gemini.embed_text(vector_text)
        await self.db.update_one(
            "student_learning_profiles",
            {"student_id": student_id},
            {
                "$setOnInsert": {
                    "_id": student_id,
                    "student_id": student_id,
                    "primary_subject": reflection["subject"],
                    "mastered_topics": [],
                    "purchased_note_ids": [],
                    "created_at": utc_now(),
                },
                "$set": {
                    "learning_style": "visual, step-by-step, frequent checks",
                    "recommendation_vector": recommendation_vector,
                    "updated_at": utc_now(),
                },
                "$addToSet": {
                    "weak_topics": {"$each": reflection.get("weaknesses", [])},
                    "session_ids": session_id,
                    "reflection_ids": reflection_id,
                    "future_ai_instructions": {"$each": reflection.get("future_ai_instructions", [])},
                    "successful_teaching_methods": {"$each": reflection.get("successful_teaching_methods", [])},
                },
            },
            upsert=True,
        )
        return await self.db.find_one("student_learning_profiles", {"student_id": student_id}) or {}

    def _mock_transcript(self, session: dict[str, Any]) -> str:
        return f"""
Tutor: Let's work on {session['subject']} through derivatives. What feels confusing?
Student: I understand the formula sometimes, but I do not get why a derivative is a slope at one exact point.
Tutor: Great. First we use two points to form a secant slope. Then we slide one point closer until the line becomes tangent.
Student: So the derivative is the slope the secant approaches?
Tutor: Exactly. For f(x)=x^2 at x=3, nearby slopes approach 6. Let's draw it and do one short check.
Student: The visual helps. I still need practice connecting the limit idea to the power rule.
"""
