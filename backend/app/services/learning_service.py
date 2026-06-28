from __future__ import annotations

import re
import uuid
from typing import Any

from backend.app.db.mongo import utc_now

# Weight for blending a new quiz score with prior mastery (exponential moving average).
MASTERY_EMA = 0.5
MASTERED_THRESHOLD = 0.8
WEAK_THRESHOLD = 0.5


def _slug(text: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_")
    return slug or "topic"


class LearningSignalService:
    """Turns real usage into measurable learning signals.

    - Micro-quizzes produce an objective mastery score per topic.
    - Mastery deltas update the student profile (weak vs mastered topics).
    - Explicit/implicit feedback assigns a reward that boosts retrieval of the
      reflections/answers that actually helped.
    """

    def __init__(self, db: Any, gemini: Any, recommendations: Any | None = None):
        self.db = db
        self.gemini = gemini
        self.recommendations = recommendations

    async def start_quiz(
        self,
        *,
        student_id: str,
        subject: str,
        topic: str,
        num_questions: int = 3,
    ) -> dict[str, Any]:
        questions, is_mock = await self.gemini.generate_quiz(
            subject=subject,
            topic=topic,
            num_questions=num_questions,
        )

        quiz_questions = []
        stored_questions = []
        for index, item in enumerate(questions):
            question_id = f"q{index + 1}"
            quiz_questions.append({"id": question_id, "question": item["question"]})
            stored_questions.append(
                {
                    "id": question_id,
                    "question": item["question"],
                    "ideal_answer": item.get("ideal_answer", ""),
                }
            )

        quiz_id = f"quiz-{uuid.uuid4().hex[:12]}"
        await self.db.insert_one(
            "quizzes",
            {
                "_id": quiz_id,
                "student_id": student_id,
                "subject": subject,
                "topic": topic,
                "questions": stored_questions,
                "status": "open",
                "content_type": "quiz",
                "created_at": utc_now(),
            },
        )

        prior_mastery = await self._topic_mastery(student_id, topic)
        return {
            "quiz_id": quiz_id,
            "subject": subject,
            "topic": topic,
            "questions": quiz_questions,
            "prior_mastery": prior_mastery,
            "is_mock": is_mock,
        }

    async def grade_quiz(self, *, quiz_id: str, answers: list[dict[str, str]]) -> dict[str, Any]:
        quiz = await self.db.find_one("quizzes", {"_id": quiz_id})
        if not quiz:
            raise ValueError("Quiz not found")

        answer_map = {a["question_id"]: a["answer"] for a in answers}
        items = [
            {
                "question": q["question"],
                "ideal_answer": q.get("ideal_answer", ""),
                "answer": answer_map.get(q["id"], ""),
            }
            for q in quiz["questions"]
        ]

        graded, is_mock = await self.gemini.grade_quiz(
            subject=quiz["subject"],
            topic=quiz["topic"],
            items=items,
        )
        score = float(graded["score"])

        student_id = quiz["student_id"]
        topic = quiz["topic"]
        prior = await self._topic_mastery(student_id, topic)
        new_mastery = round(score if prior <= 0 else (MASTERY_EMA * prior + (1 - MASTERY_EMA) * score), 3)
        delta = round(new_mastery - prior, 3)
        mastered = new_mastery >= MASTERED_THRESHOLD

        profile = await self._apply_mastery(
            student_id=student_id,
            topic=topic,
            subject=quiz["subject"],
            new_mastery=new_mastery,
            mastered=mastered,
        )

        await self.db.update_one(
            "quizzes",
            {"_id": quiz_id},
            {"$set": {"status": "graded", "score": score, "graded_at": utc_now()}},
        )
        await self.db.insert_one(
            "learning_events",
            {
                "_id": f"event-{uuid.uuid4().hex[:12]}",
                "student_id": student_id,
                "type": "quiz_mastery",
                "subject": quiz["subject"],
                "topic": topic,
                "score": score,
                "prior_mastery": prior,
                "new_mastery": new_mastery,
                "delta": delta,
                "mastered": mastered,
                "content_type": "learning_event",
                "created_at": utc_now(),
            },
        )
        if self.recommendations:
            await self.recommendations.refresh_for_student(student_id)

        return {
            "quiz_id": quiz_id,
            "subject": quiz["subject"],
            "topic": topic,
            "score": round(score, 3),
            "prior_mastery": prior,
            "new_mastery": new_mastery,
            "delta": delta,
            "mastered": mastered,
            "per_question": graded["per_question"],
            "weak_topics": profile.get("weak_topics", []),
            "mastered_topics": profile.get("mastered_topics", []),
            "is_mock": is_mock,
        }

    async def record_feedback(
        self,
        *,
        conversation_id: str,
        student_id: str,
        helpful: bool,
        note: str | None = None,
    ) -> dict[str, Any]:
        conversation = await self.db.find_one("ai_conversations", {"_id": conversation_id})
        if not conversation:
            raise ValueError("Conversation not found")

        reward = 1.0 if helpful else -1.0
        await self.db.update_one(
            "ai_conversations",
            {"_id": conversation_id},
            {"$set": {"helpful": helpful, "reward": reward, "feedback_note": note, "feedback_at": utc_now()}},
        )

        # Propagate the reward to any reflection derived from this conversation so
        # that retrieval favors memories that actually helped the student.
        await self.db.update_one(
            "ai_reflections",
            {"conversation_id": conversation_id},
            {"$set": {"reward": reward}},
        )

        await self.db.insert_one(
            "learning_events",
            {
                "_id": f"event-{uuid.uuid4().hex[:12]}",
                "student_id": student_id,
                "type": "feedback",
                "conversation_id": conversation_id,
                "helpful": helpful,
                "reward": reward,
                "note": note,
                "content_type": "learning_event",
                "created_at": utc_now(),
            },
        )

        message = (
            "Thanks - I'll remember this approach worked and surface it more often."
            if helpful
            else "Got it - I'll rely on this answer less and try a different approach next time."
        )
        return {"conversation_id": conversation_id, "helpful": helpful, "reward": reward, "message": message}

    async def _topic_mastery(self, student_id: str, topic: str) -> float:
        profile = await self.db.find_one("student_learning_profiles", {"student_id": student_id}) or {}
        mastery = profile.get("topic_mastery", {}) or {}
        return float(mastery.get(_slug(topic), 0.0))

    async def _apply_mastery(
        self,
        *,
        student_id: str,
        topic: str,
        subject: str,
        new_mastery: float,
        mastered: bool,
    ) -> dict[str, Any]:
        update: dict[str, Any] = {
            "$set": {
                f"topic_mastery.{_slug(topic)}": new_mastery,
                "updated_at": utc_now(),
            },
            "$setOnInsert": {
                "_id": student_id,
                "student_id": student_id,
                "primary_subject": subject,
                "created_at": utc_now(),
            },
        }
        if mastered:
            update["$addToSet"] = {"mastered_topics": topic}
            update["$pull"] = {"weak_topics": topic}
        elif new_mastery < WEAK_THRESHOLD:
            update["$addToSet"] = {"weak_topics": topic}

        await self.db.update_one("student_learning_profiles", {"student_id": student_id}, update, upsert=True)
        return await self.db.find_one("student_learning_profiles", {"student_id": student_id}) or {}
