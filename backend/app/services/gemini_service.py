from __future__ import annotations

import asyncio
import hashlib
import json
import math
import re
from typing import Any

from backend.app.services.weave_service import (
    safe_trace,
    trace_ai_tutor_response,
    trace_embedding,
    trace_quiz_generation,
    trace_quiz_grading,
    trace_reflection,
)


class GeminiService:
    """Gemini wrapper with deterministic mock fallbacks for demos."""

    def __init__(self, settings: Any):
        self.settings = settings
        self.client = None
        self.is_mock = not settings.gemini_api_key
        if settings.gemini_api_key:
            try:
                # Sponsor integration: Gemini generates tutoring responses,
                # session summaries, quiz ideas, reflections, and embeddings.
                from google import genai

                self.client = genai.Client(api_key=settings.gemini_api_key)
                self.is_mock = False
            except Exception:
                self.is_mock = True

    async def embed_text(self, text: str) -> list[float]:
        is_mock = True
        if self.client:
            try:
                embedding = await asyncio.to_thread(self._embed_with_gemini, text)
                is_mock = False
                if self.settings.weave_trace_embeddings:
                    safe_trace(
                        trace_embedding,
                        model=self.settings.gemini_embedding_model,
                        text=text,
                        dimensions=len(embedding),
                        is_mock=is_mock,
                    )
                return embedding
            except Exception:
                pass
        embedding = self._mock_embedding(text)
        if self.settings.weave_trace_embeddings:
            safe_trace(
                trace_embedding,
                model="mock-embedding",
                text=text,
                dimensions=len(embedding),
                is_mock=is_mock,
            )
        return embedding

    def _embed_with_gemini(self, text: str) -> list[float]:
        response = self.client.models.embed_content(
            model=self.settings.gemini_embedding_model,
            contents=text,
        )
        embedding = response.embeddings[0].values
        return self._normalize(embedding[: self.settings.embedding_dimensions])

    async def generate_tutor_response(
        self,
        *,
        question: str,
        student_profile: dict[str, Any] | None,
        retrieved_context: list[dict[str, Any]],
        language: str = "English",
    ) -> tuple[str, bool]:
        prompt = self._build_tutor_prompt(question, student_profile, retrieved_context, language)
        answer: str | None = None
        is_mock = True
        if self.client:
            try:
                response = await asyncio.to_thread(
                    self.client.models.generate_content,
                    model=self.settings.gemini_model,
                    contents=prompt,
                )
                answer = response.text
                is_mock = False
            except Exception:
                pass
        if answer is None:
            answer = self._mock_tutor_response(question, student_profile, retrieved_context, language)
        safe_trace(
            trace_ai_tutor_response,
            model=self.settings.gemini_model if not is_mock else "mock-tutor",
            question=question,
            language=language,
            weak_topics=(student_profile or {}).get("weak_topics", []),
            retrieved_context=retrieved_context,
            answer=answer,
            is_mock=is_mock,
        )
        return answer, is_mock

    async def reflect_session(
        self,
        *,
        transcript: str,
        subject: str,
        target_language: str,
        session_type: str = "human",
    ) -> tuple[dict[str, Any], bool]:
        session_label = "human tutoring" if session_type == "human" else "AI tutoring"
        prompt = f"""
You are the continual-learning engine for TutorLoop.
Analyze this {session_label} session transcript. Do not suggest fine-tuning model weights.
Return strict JSON with these keys:
summary, translated_summary, weaknesses, successful_teaching_methods,
future_ai_instructions, quiz_results, recommendation_text.

Subject: {subject}
Session type: {session_type}
Translate the summary to: {target_language}

Transcript:
{transcript}
"""
        reflection: dict[str, Any] | None = None
        is_mock = True
        if self.client:
            try:
                response = await asyncio.to_thread(
                    self.client.models.generate_content,
                    model=self.settings.gemini_model,
                    contents=prompt,
                )
                reflection = self._parse_reflection_json(response.text)
                is_mock = False
            except Exception:
                pass
        if reflection is None:
            reflection = self._mock_reflection(transcript, subject, target_language)
        safe_trace(
            trace_reflection,
            model=self.settings.gemini_model if not is_mock else "mock-reflection",
            subject=subject,
            target_language=target_language,
            session_type=session_type,
            transcript=transcript,
            reflection=reflection,
            is_mock=is_mock,
        )
        return reflection, is_mock

    async def generate_quiz(
        self,
        *,
        subject: str,
        topic: str,
        num_questions: int = 3,
    ) -> tuple[list[dict[str, Any]], bool]:
        """Generate a short diagnostic quiz for a topic. Returns (questions, is_mock)."""
        prompt = f"""
You are TutorLoop's diagnostic quiz writer.
Write {num_questions} short open-ended questions that measure a student's understanding
of the topic below. Questions should be answerable in 1-2 sentences and progress from
basic recall to applied reasoning.

Subject: {subject}
Topic: {topic}

Return strict JSON: {{"questions": [{{"question": "...", "ideal_answer": "..."}}]}}
"""
        questions: list[dict[str, Any]] | None = None
        is_mock = True
        if self.client:
            try:
                response = await asyncio.to_thread(
                    self.client.models.generate_content,
                    model=self.settings.gemini_model,
                    contents=prompt,
                )
                parsed = self._extract_json(response.text)
                candidate_questions = [
                    {"question": str(q.get("question", "")).strip(), "ideal_answer": str(q.get("ideal_answer", "")).strip()}
                    for q in parsed.get("questions", [])
                    if str(q.get("question", "")).strip()
                ]
                if candidate_questions:
                    questions = candidate_questions[:num_questions]
                    is_mock = False
            except Exception:
                pass
        if questions is None:
            questions = self._mock_quiz(subject, topic, num_questions)
        safe_trace(
            trace_quiz_generation,
            model=self.settings.gemini_model if not is_mock else "mock-quiz",
            subject=subject,
            topic=topic,
            questions=questions,
            is_mock=is_mock,
        )
        return questions, is_mock

    async def grade_quiz(
        self,
        *,
        subject: str,
        topic: str,
        items: list[dict[str, Any]],
    ) -> tuple[dict[str, Any], bool]:
        """Grade quiz answers. items: [{question, ideal_answer, answer}].

        Returns ({score: 0..1, per_question: [{question, correct, feedback, score}]}, is_mock).
        """
        joined = "\n".join(
            f"Q{i + 1}: {item.get('question', '')}\nIdeal: {item.get('ideal_answer', '')}\nStudent: {item.get('answer', '')}"
            for i, item in enumerate(items)
        )
        prompt = f"""
You are TutorLoop's grader for a {subject} quiz on "{topic}".
Grade each student answer for conceptual correctness from 0.0 to 1.0 (partial credit allowed).
Be encouraging but accurate. Return strict JSON:
{{"per_question": [{{"score": 0.0, "correct": true, "feedback": "..."}}]}}

{joined}
"""
        grade: dict[str, Any] | None = None
        is_mock = True
        if self.client:
            try:
                response = await asyncio.to_thread(
                    self.client.models.generate_content,
                    model=self.settings.gemini_model,
                    contents=prompt,
                )
                parsed = self._extract_json(response.text)
                per_question = []
                for i, graded in enumerate(parsed.get("per_question", [])):
                    score = max(0.0, min(1.0, float(graded.get("score", 0))))
                    per_question.append(
                        {
                            "question": items[i].get("question", "") if i < len(items) else "",
                            "score": score,
                            "correct": bool(graded.get("correct", score >= 0.6)),
                            "feedback": str(graded.get("feedback", "")),
                        }
                    )
                if per_question:
                    overall = sum(q["score"] for q in per_question) / len(per_question)
                    grade = {"score": round(overall, 3), "per_question": per_question}
                    is_mock = False
            except Exception:
                pass
        if grade is None:
            grade = self._mock_grade(items)
        safe_trace(
            trace_quiz_grading,
            model=self.settings.gemini_model if not is_mock else "mock-grader",
            subject=subject,
            topic=topic,
            items=items,
            grade=grade,
            is_mock=is_mock,
        )
        return grade, is_mock

    def _extract_json(self, text: str) -> dict[str, Any]:
        match = re.search(r"\{.*\}", text, re.DOTALL)
        if not match:
            raise ValueError("Gemini did not return JSON")
        return json.loads(match.group(0))

    def _mock_quiz(self, subject: str, topic: str, num_questions: int) -> list[dict[str, Any]]:
        bank = [
            {"question": f"In your own words, what is the core idea of {topic}?",
             "ideal_answer": f"A correct, concise explanation of the central concept of {topic}."},
            {"question": f"Give one concrete example that illustrates {topic}.",
             "ideal_answer": f"A relevant worked example demonstrating {topic}."},
            {"question": f"What is a common mistake students make with {topic}, and how do you avoid it?",
             "ideal_answer": f"Identifies a typical {topic} pitfall and a correction strategy."},
            {"question": f"How does {topic} connect to the broader subject of {subject}?",
             "ideal_answer": f"Links {topic} to related ideas in {subject}."},
        ]
        return bank[: max(1, min(num_questions, len(bank)))]

    def _mock_grade(self, items: list[dict[str, Any]]) -> dict[str, Any]:
        per_question = []
        for item in items:
            answer = str(item.get("answer", "")).strip()
            words = len(answer.split())
            # Heuristic: longer, non-trivial answers score higher in demo mode.
            if words == 0:
                score = 0.0
            elif words < 5:
                score = 0.4
            elif words < 15:
                score = 0.7
            else:
                score = 0.9
            per_question.append(
                {
                    "question": item.get("question", ""),
                    "score": score,
                    "correct": score >= 0.6,
                    "feedback": "Demo grading: answer scored on depth and specificity. Add a concrete example to improve."
                    if score < 0.9
                    else "Demo grading: strong, specific answer.",
                }
            )
        overall = (sum(q["score"] for q in per_question) / len(per_question)) if per_question else 0.0
        return {"score": round(overall, 3), "per_question": per_question}

    def _build_tutor_prompt(
        self,
        question: str,
        student_profile: dict[str, Any] | None,
        retrieved_context: list[dict[str, Any]],
        language: str,
    ) -> str:
        context = "\n\n".join(
            f"[{item.get('collection')}] {item.get('title')}: {item.get('snippet') or item.get('content') or item.get('summary')}"
            for item in retrieved_context
        )
        return f"""
You are TutorLoop's AI tutor. Teach in a warm, Socratic, tutoring style.
Use retrieved platform books, tutor notes, session reflections, student weak topics, and profile memory.
When book chunks are retrieved, cite the book title and ground explanations in that material.
Do not claim model weights were fine-tuned; explain that you improve through memory,
retrieval, reflection, and prompt optimization.

Language: {language}
Student profile: {json.dumps(student_profile or {}, default=str)}
Retrieved context:
{context}

Student question: {question}

Answer with:
1. A direct explanation
2. One worked example
3. A quick check question
4. A note about what you are remembering for future sessions
"""

    def _parse_reflection_json(self, text: str) -> dict[str, Any]:
        match = re.search(r"\{.*\}", text, re.DOTALL)
        if not match:
            raise ValueError("Gemini did not return JSON")
        parsed = json.loads(match.group(0))
        return {
            "summary": str(parsed.get("summary", "")),
            "translated_summary": str(parsed.get("translated_summary", parsed.get("summary", ""))),
            "weaknesses": list(parsed.get("weaknesses", [])),
            "successful_teaching_methods": list(parsed.get("successful_teaching_methods", [])),
            "future_ai_instructions": list(parsed.get("future_ai_instructions", [])),
            "quiz_results": parsed.get("quiz_results", {}),
            "recommendation_text": str(parsed.get("recommendation_text", "")),
        }

    def _mock_tutor_response(
        self,
        question: str,
        student_profile: dict[str, Any] | None,
        retrieved_context: list[dict[str, Any]],
        language: str,
    ) -> str:
        weak_topics = ", ".join((student_profile or {}).get("weak_topics", [])[:4]) or "the current topic"
        context_titles = ", ".join(item.get("title", "matched resource") for item in retrieved_context[:3])
        derivative_mode = "derivative" in question.lower() or "derivatives" in question.lower()

        if derivative_mode:
            answer = (
                "Think of a derivative as an instant slope: it tells you how fast a function is changing at one point. "
                "For f(x) = x^2, compare tiny changes near x = 3. The slope gets close to 6, so f'(3) = 6. "
                "A human tutor note from your profile says step-by-step graph reasoning worked well for you, so I would draw the curve, "
                "zoom into x = 3, and show the tangent line becoming the local slope. "
                "Quick check: if f(x) = 4x^2, what is f'(x), and what is the slope at x = 2?"
            )
        else:
            answer = (
                f"I found related TutorLoop context from {context_titles or 'your learning history'}. "
                f"Your current weak-topic memory includes {weak_topics}. "
                "Let's break the question into the definition, a worked example, and a check question so the next answer can adapt."
            )

        if language.lower() != "english":
            answer = f"[{language} demo translation] {answer}"
        return answer + " I am storing this interaction as retrieval memory, not changing model weights."

    def _mock_reflection(self, transcript: str, subject: str, target_language: str) -> dict[str, Any]:
        lower = transcript.lower()
        weaknesses = []
        if "derivative" in lower or "slope" in lower:
            weaknesses.extend(["derivatives as instant rate of change", "connecting secant slope to tangent slope"])
        if "chain rule" in lower:
            weaknesses.append("chain rule setup")
        if not weaknesses:
            weaknesses.append(f"{subject} foundations")

        methods = ["used graph-first explanations", "asked short diagnostic questions", "connected formulas to a concrete example"]
        summary = (
            f"The student practiced {subject} and needed extra support with {', '.join(weaknesses)}. "
            "The tutor's strongest move was slowing the lesson down into a visual example, then checking understanding."
        )
        translated = summary
        if target_language.lower() == "spanish":
            translated = (
                f"El estudiante practico {subject} y necesito apoyo con {', '.join(weaknesses)}. "
                "El tutor uso una explicacion visual paso a paso y verifico la comprension."
            )
        elif target_language.lower() != "english":
            translated = f"[{target_language} demo translation] {summary}"

        return {
            "summary": summary,
            "translated_summary": translated,
            "weaknesses": weaknesses,
            "successful_teaching_methods": methods,
            "future_ai_instructions": [
                "Start derivative lessons with a visual slope intuition before rules.",
                "Ask one quick check question every 2-3 steps.",
                "Use the student's own confusion about secant vs tangent slope as retrieval memory.",
            ],
            "quiz_results": {"derivative_intuition": "needs_practice", "power_rule": "emerging"},
            "recommendation_text": "Recommend derivative notes, a calculus tutor, and an AI lesson on tangent slope intuition.",
        }

    def _mock_embedding(self, text: str) -> list[float]:
        dimensions = self.settings.embedding_dimensions
        features = [0.0] * dimensions
        lower = text.lower()
        concept_groups = [
            ("derivative", ["derivative", "slope", "tangent", "secant", "rate of change", "calculus"]),
            ("integral", ["integral", "area", "antiderivative"]),
            ("algebra", ["algebra", "equation", "linear", "quadratic"]),
            ("physics", ["force", "motion", "velocity", "acceleration"]),
            ("biology", ["cell", "genetics", "biology"]),
            ("essay", ["essay", "writing", "thesis", "paragraph"]),
        ]
        for index, (_, terms) in enumerate(concept_groups):
            if any(term in lower for term in terms):
                features[index] = 1.0

        digest = hashlib.sha256(text.encode("utf-8")).digest()
        for index in range(len(concept_groups), dimensions):
            byte = digest[index % len(digest)]
            features[index] = (byte / 255.0) - 0.5
        return self._normalize(features)

    def _normalize(self, values: list[float]) -> list[float]:
        if len(values) < self.settings.embedding_dimensions:
            values = values + [0.0] * (self.settings.embedding_dimensions - len(values))
        magnitude = math.sqrt(sum(value * value for value in values)) or 1.0
        return [float(value / magnitude) for value in values[: self.settings.embedding_dimensions]]
