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
        result = await self._run_reflection(
            student_id=session["student_id"],
            subject=session["subject"],
            transcript=transcript_text,
            target_language=target_language,
            source="human",
            session_id=session_id,
            tutor_id=session.get("tutor_id"),
            transcript_source="mock" if transcript is None else "uploaded",
        )

        await self.db.update_one(
            "sessions",
            {"_id": session_id},
            {
                "$set": {
                    "status": "reflected",
                    "transcript_id": result["transcript_id"],
                    "reflection_id": result["reflection_id"],
                }
            },
        )
        await self.db.update_one(
            "bookings",
            {"_id": session["booking_id"]},
            {"$set": {"status": "reflected"}},
        )
        return result

    async def reflect_ai_conversation(
        self,
        *,
        conversation_id: str,
        target_language: str,
    ) -> dict[str, Any]:
        conversation = await self.db.find_one("ai_conversations", {"_id": conversation_id})
        if not conversation:
            raise ValueError("AI conversation not found")
        if conversation.get("status") == "reflected":
            raise ValueError("AI conversation already reflected")

        transcript_text = self._transcript_from_conversation(conversation)
        result = await self._run_reflection(
            student_id=conversation["student_id"],
            subject=conversation.get("subject") or "General",
            transcript=transcript_text,
            target_language=target_language,
            source="ai",
            conversation_id=conversation_id,
            transcript_source="ai_chat",
        )

        await self.db.update_one(
            "ai_conversations",
            {"_id": conversation_id},
            {
                "$set": {
                    "status": "reflected",
                    "transcript_id": result["transcript_id"],
                    "reflection_id": result["reflection_id"],
                }
            },
        )
        return result

    async def _run_reflection(
        self,
        *,
        student_id: str,
        subject: str,
        transcript: str,
        target_language: str,
        source: str,
        session_id: str | None = None,
        conversation_id: str | None = None,
        tutor_id: str | None = None,
        transcript_source: str,
    ) -> dict[str, Any]:
        transcript_doc = {
            "session_id": session_id,
            "conversation_id": conversation_id,
            "student_id": student_id,
            "tutor_id": tutor_id,
            "subject": subject,
            "transcript": transcript,
            "language": "English",
            "source": transcript_source,
            "session_source": source,
            "content_type": "transcript",
        }
        transcript_doc["embedding"] = await self.vector_search.embed_document(
            transcript_doc,
            ["subject", "transcript"],
        )
        transcript_id = await self.db.insert_one("transcripts", transcript_doc)

        reflection, is_mock = await self.gemini.reflect_session(
            transcript=transcript,
            subject=subject,
            target_language=target_language,
            session_type=source,
        )

        reflection_doc = {
            "session_id": session_id,
            "conversation_id": conversation_id,
            "transcript_id": transcript_id,
            "student_id": student_id,
            "tutor_id": tutor_id,
            "subject": subject,
            "summary": reflection["summary"],
            "translated_summary": reflection["translated_summary"],
            "weaknesses": reflection["weaknesses"],
            "successful_teaching_methods": reflection["successful_teaching_methods"],
            "future_ai_instructions": reflection["future_ai_instructions"],
            "quiz_results": reflection["quiz_results"],
            "recommendation_text": reflection["recommendation_text"],
            "session_source": source,
            "content_type": "ai_reflection",
            "created_at": utc_now(),
        }
        reflection_doc["embedding"] = await self.vector_search.embed_document(
            reflection_doc,
            ["subject", "summary", "recommendation_text"],
        )
        reflection_id = await self.db.insert_one("ai_reflections", reflection_doc)

        updated_profile = await self._update_student_profile(
            student_id=student_id,
            session_id=session_id,
            conversation_id=conversation_id,
            reflection_id=reflection_id,
            reflection=reflection_doc,
        )
        await self.recommendations.refresh_for_student(student_id)

        return {
            "reflection_id": reflection_id,
            "transcript_id": transcript_id,
            "session_id": session_id,
            "conversation_id": conversation_id,
            "student_id": student_id,
            "source": source,
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
        session_id: str | None,
        conversation_id: str | None,
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
        add_to_set: dict[str, Any] = {
            "weak_topics": {"$each": reflection.get("weaknesses", [])},
            "reflection_ids": reflection_id,
            "future_ai_instructions": {"$each": reflection.get("future_ai_instructions", [])},
            "successful_teaching_methods": {"$each": reflection.get("successful_teaching_methods", [])},
        }
        if session_id:
            add_to_set["session_ids"] = session_id
        if conversation_id:
            add_to_set["ai_conversation_ids"] = conversation_id

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
                    "purchased_book_ids": [],
                    "created_at": utc_now(),
                },
                "$set": {
                    "learning_style": "visual, step-by-step, frequent checks",
                    "recommendation_vector": recommendation_vector,
                    "updated_at": utc_now(),
                },
                "$addToSet": add_to_set,
            },
            upsert=True,
        )
        return await self.db.find_one("student_learning_profiles", {"student_id": student_id}) or {}

    def _transcript_from_conversation(self, conversation: dict[str, Any]) -> str:
        return (
            f"Student: {conversation.get('question', '').strip()}\n"
            f"AI Tutor: {conversation.get('answer', '').strip()}"
        )

    def _mock_transcript(self, session: dict[str, Any]) -> str:
        return f"""
Tutor: Let's work on {session['subject']} through derivatives. What feels confusing?
Student: I understand the formula sometimes, but I do not get why a derivative is a slope at one exact point.
Tutor: Great. First we use two points to form a secant slope. Then we slide one point closer until the line becomes tangent.
Student: So the derivative is the slope the secant approaches?
Tutor: Exactly. For f(x)=x^2 at x=3, nearby slopes approach 6. Let's draw it and do one short check.
Student: The visual helps. I still need practice connecting the limit idea to the power rule.
"""
