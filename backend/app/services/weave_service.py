from __future__ import annotations

import hashlib
import os
from typing import Any, Callable

try:
    import weave
except Exception:  # Weave is optional for local hackathon demos.
    weave = None


_enabled = False
_status = "disabled"


def init_weave(settings: Any) -> str:
    """Initialize W&B Weave tracing when explicitly enabled.

    Sponsor integration: Weave captures AI tutor, reflection, quiz, and optional
    embedding traces for demo observability. TutorLoop still runs without Weave.
    """
    global _enabled, _status

    if not getattr(settings, "weave_enabled", False):
        _enabled = False
        _status = "disabled"
        return _status

    if weave is None:
        _enabled = False
        _status = "missing_package"
        return _status

    wandb_api_key = getattr(settings, "wandb_api_key", None)
    if wandb_api_key and not os.environ.get("WANDB_API_KEY"):
        os.environ["WANDB_API_KEY"] = wandb_api_key

    project = settings.weave_project
    if getattr(settings, "weave_entity", None):
        project = f"{settings.weave_entity}/{project}"

    try:
        weave.init(project)
        _enabled = True
        _status = f"enabled:{project}"
    except Exception as exc:  # noqa: BLE001 - observability should not break the app.
        _enabled = False
        _status = f"error:{exc.__class__.__name__}"
    return _status


def get_weave_status() -> str:
    return _status


def weave_op(func: Callable) -> Callable:
    if weave is None:
        return func
    return weave.op()(func)


def safe_trace(func: Callable, *args: Any, **kwargs: Any) -> Any:
    if not _enabled:
        return None
    try:
        return func(*args, **kwargs)
    except Exception:
        return None


def _preview(value: str, limit: int = 1600) -> str:
    value = value or ""
    return value if len(value) <= limit else value[:limit] + "..."


def _context_preview(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "id": str(item.get("id") or item.get("_id") or ""),
            "collection": item.get("collection"),
            "title": item.get("title"),
            "content_type": item.get("content_type"),
            "score": item.get("score"),
        }
        for item in items[:10]
    ]


@weave_op
def trace_ai_tutor_response(
    *,
    model: str,
    question: str,
    language: str,
    weak_topics: list[str],
    retrieved_context: list[dict[str, Any]],
    answer: str,
    is_mock: bool,
) -> dict[str, Any]:
    return {
        "operation": "ai_tutor_response",
        "model": model,
        "question": question,
        "language": language,
        "weak_topics": weak_topics[:8],
        "retrieved_context": _context_preview(retrieved_context),
        "answer": _preview(answer),
        "is_mock": is_mock,
    }


@weave_op
def trace_reflection(
    *,
    model: str,
    subject: str,
    target_language: str,
    session_type: str,
    transcript: str,
    reflection: dict[str, Any],
    is_mock: bool,
) -> dict[str, Any]:
    return {
        "operation": "continual_learning_reflection",
        "model": model,
        "subject": subject,
        "target_language": target_language,
        "session_type": session_type,
        "transcript_preview": _preview(transcript),
        "reflection": reflection,
        "is_mock": is_mock,
    }


@weave_op
def trace_quiz_generation(
    *,
    model: str,
    subject: str,
    topic: str,
    questions: list[dict[str, Any]],
    is_mock: bool,
) -> dict[str, Any]:
    return {
        "operation": "quiz_generation",
        "model": model,
        "subject": subject,
        "topic": topic,
        "questions": questions,
        "is_mock": is_mock,
    }


@weave_op
def trace_quiz_grading(
    *,
    model: str,
    subject: str,
    topic: str,
    items: list[dict[str, Any]],
    grade: dict[str, Any],
    is_mock: bool,
) -> dict[str, Any]:
    return {
        "operation": "quiz_grading",
        "model": model,
        "subject": subject,
        "topic": topic,
        "items": [
            {
                "question": item.get("question"),
                "answer": _preview(str(item.get("answer", "")), 500),
            }
            for item in items
        ],
        "grade": grade,
        "is_mock": is_mock,
    }


@weave_op
def trace_embedding(
    *,
    model: str,
    text: str,
    dimensions: int,
    is_mock: bool,
) -> dict[str, Any]:
    return {
        "operation": "embedding",
        "model": model,
        "text_sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
        "text_preview": _preview(text, 500),
        "dimensions": dimensions,
        "is_mock": is_mock,
    }


@weave_op
def trace_ai_lecture_start(
    *,
    student_id: str,
    subject: str,
    topic: str,
    room_id: str,
    grounded_sources: bool,
    notes: list[dict[str, Any]],
    is_mock: bool,
) -> dict[str, Any]:
    return {
        "operation": "ai_lecture_start",
        "student_id": student_id,
        "subject": subject,
        "topic": topic,
        "room_id": room_id,
        "grounded_sources": grounded_sources,
        "notes": _context_preview(notes),
        "is_mock": is_mock,
    }
