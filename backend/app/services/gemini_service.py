from __future__ import annotations

import asyncio
import hashlib
import json
import math
import re
from typing import Any


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
        if self.client:
            try:
                return await asyncio.to_thread(self._embed_with_gemini, text)
            except Exception:
                return self._mock_embedding(text)
        return self._mock_embedding(text)

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
        if self.client:
            try:
                response = await asyncio.to_thread(
                    self.client.models.generate_content,
                    model=self.settings.gemini_model,
                    contents=prompt,
                )
                return response.text, False
            except Exception:
                pass
        return self._mock_tutor_response(question, student_profile, retrieved_context, language), True

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
        if self.client:
            try:
                response = await asyncio.to_thread(
                    self.client.models.generate_content,
                    model=self.settings.gemini_model,
                    contents=prompt,
                )
                return self._parse_reflection_json(response.text), False
            except Exception:
                pass
        return self._mock_reflection(transcript, subject, target_language), True

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
