from __future__ import annotations

import argparse
import asyncio
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

import weave

from backend.app.core.config import get_settings
from backend.app.db.mongo import AppDatabase
from backend.app.services.gemini_service import GeminiService
from backend.app.services.vector_search import VectorSearchService
from backend.app.services.weave_service import get_weave_status, init_weave


AI_RETRIEVAL_COLLECTIONS = [
    "books",
    "book_chunks",
    "notes",
    "tutors",
    "ai_reflections",
    "transcripts",
    "ai_conversations",
]


EVAL_ROWS: list[dict[str, Any]] = [
    {
        "case_id": "baseline_derivative_tangent_slope",
        "phase": "baseline",
        "student_id": "eval-student-baseline",
        "question": "I am confused about derivatives. Why is a derivative the slope at one point?",
        "subject": "Calculus",
        "language": "English",
        "weak_topics": [],
        "future_ai_instructions": [],
        "reflection_memory": "",
        "expected_terms": ["derivative", "slope", "tangent", "example"],
        "target_memory_terms": [],
        "expected_collections": ["notes", "books", "book_chunks", "tutors", "ai_reflections"],
        "min_context_count": 2,
        "forbidden_claims": ["fine-tuned my weights", "changed my weights", "trained my weights"],
    },
    {
        "case_id": "after_reflection_derivative_visual",
        "phase": "after_reflection",
        "student_id": "eval-student-after-reflection",
        "question": "Use what my human tutor noticed to explain derivatives and tangent slope.",
        "subject": "Calculus",
        "language": "English",
        "weak_topics": [
            "connecting secant slope to tangent slope",
            "derivatives as instant rate of change",
        ],
        "future_ai_instructions": [
            "Start derivative lessons with graph-first visual intuition.",
            "Use the secant-to-tangent transition before derivative rules.",
            "Ask one short check question every few steps.",
        ],
        "reflection_memory": (
            "Human tutor reflection: the student understood derivatives better when the tutor drew "
            "secant lines sliding into a tangent line, then used f(x)=x^2 at x=3 as a worked example. "
            "Future AI instruction: begin with visual slope intuition and ask a quick check question."
        ),
        "expected_terms": ["secant", "tangent", "slope", "check"],
        "target_memory_terms": ["visual", "secant", "tangent"],
        "expected_collections": ["ai_reflections", "notes", "books", "book_chunks"],
        "min_context_count": 3,
        "forbidden_claims": ["fine-tuned my weights", "changed my weights", "trained my weights"],
    },
    {
        "case_id": "after_reflection_chain_rule",
        "phase": "after_reflection",
        "student_id": "eval-student-chain-rule",
        "question": "I keep mixing up the chain rule. Teach it like my tutor would.",
        "subject": "Calculus",
        "language": "English",
        "weak_topics": ["chain rule setup", "identifying inner and outer functions"],
        "future_ai_instructions": [
            "Have the student label the outside function and inside function before differentiating.",
            "Use a short diagnostic question before giving the final derivative.",
        ],
        "reflection_memory": (
            "Human tutor reflection: the student succeeds when they label outer and inner functions "
            "with two colors before applying the chain rule. The tutor asked short diagnostic questions."
        ),
        "expected_terms": ["chain rule", "inside", "outside", "example"],
        "target_memory_terms": ["inner", "outer", "diagnostic"],
        "expected_collections": ["ai_reflections", "notes", "books", "book_chunks", "tutors"],
        "min_context_count": 2,
        "forbidden_claims": ["fine-tuned my weights", "changed my weights", "trained my weights"],
    },
    {
        "case_id": "recommend_next_practice",
        "phase": "after_reflection",
        "student_id": "eval-student-next-practice",
        "question": "What should I practice next if derivatives still feel shaky?",
        "subject": "Calculus",
        "language": "English",
        "weak_topics": ["derivative intuition", "power rule fluency", "tangent line interpretation"],
        "future_ai_instructions": [
            "Recommend one small practice sequence, not a broad study plan.",
            "Connect recommendations to weak topics from prior sessions.",
        ],
        "reflection_memory": (
            "Human tutor reflection: the student needs a focused progression: derivative intuition, "
            "then power rule fluency, then tangent line word problems."
        ),
        "expected_terms": ["practice", "derivative", "power rule", "tangent"],
        "target_memory_terms": ["weak", "practice", "power rule"],
        "expected_collections": ["ai_reflections", "notes", "books", "book_chunks"],
        "min_context_count": 2,
        "forbidden_claims": ["fine-tuned my weights", "changed my weights", "trained my weights"],
    },
]


@dataclass
class EvalContext:
    db: AppDatabase
    gemini: GeminiService
    vector_search: VectorSearchService


EVAL_CONTEXT: EvalContext | None = None


def _context() -> EvalContext:
    if EVAL_CONTEXT is None:
        raise RuntimeError("Eval context is not initialized")
    return EVAL_CONTEXT


def _contains_any(text: str, terms: list[str]) -> bool:
    lower = text.lower()
    return any(term.lower() in lower for term in terms)


def _term_coverage(text: str, terms: list[str]) -> tuple[float, list[str]]:
    if not terms:
        return 1.0, []
    lower = text.lower()
    matched = [term for term in terms if term.lower() in lower]
    return round(len(matched) / len(terms), 3), matched


def _shape_retrieved_context(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    shaped = []
    for item in items[:8]:
        shaped.append(
            {
                "id": str(item.get("id") or item.get("_id") or ""),
                "collection": item.get("collection"),
                "title": item.get("title"),
                "score": item.get("score"),
                "content_type": item.get("content_type"),
            }
        )
    return shaped


@weave.op()
async def tutorloop_ai_tutor_eval(
    case_id: str,
    phase: str,
    student_id: str,
    question: str,
    subject: str,
    language: str,
    weak_topics: list[str],
    future_ai_instructions: list[str],
    reflection_memory: str,
) -> dict[str, Any]:
    """Run the same RAG + Gemini answer path used by TutorLoop's AI tutor."""
    ctx = _context()
    profile = {
        "student_id": student_id,
        "primary_subject": subject,
        "weak_topics": weak_topics,
        "future_ai_instructions": future_ai_instructions,
        "learning_style": "visual, step-by-step, frequent checks" if phase == "after_reflection" else "",
    }

    retrieved = await ctx.vector_search.search(
        query=question,
        collections=AI_RETRIEVAL_COLLECTIONS,
        filters={"subject": subject},
        limit=7,
    )
    if reflection_memory:
        retrieved.insert(
            0,
            {
                "id": f"{case_id}-synthetic-reflection",
                "collection": "ai_reflections",
                "content_type": "ai_reflection",
                "title": "Synthetic human tutor reflection for eval",
                "snippet": reflection_memory,
                "summary": reflection_memory,
                "score": 1.0,
            },
        )

    answer, is_mock = await ctx.gemini.generate_tutor_response(
        question=question,
        student_profile=profile,
        retrieved_context=retrieved,
        language=language,
    )
    return {
        "answer": answer,
        "is_mock": is_mock,
        "phase": phase,
        "retrieved_context": _shape_retrieved_context(retrieved),
        "used_reflection_memory": bool(reflection_memory),
    }


@weave.op()
def expected_terms_score(output: dict[str, Any], expected_terms: list[str]) -> dict[str, Any]:
    answer = str(output.get("answer", ""))
    score, matched = _term_coverage(answer, expected_terms)
    return {"score": score, "matched_terms": matched, "expected_terms": expected_terms}


@weave.op()
def pedagogy_score(output: dict[str, Any]) -> dict[str, Any]:
    answer = str(output.get("answer", ""))
    lower = answer.lower()
    checks = {
        "direct_explanation": _contains_any(lower, ["derivative", "means", "is the", "tells you"]),
        "worked_example": _contains_any(lower, ["example", "for f(", "worked", "suppose", "let"]),
        "quick_check": _contains_any(lower, ["quick check", "your turn", "try", "question"]),
        "future_memory_note": _contains_any(lower, ["remember", "memory", "future", "next session"]),
    }
    score = round(sum(1 for passed in checks.values() if passed) / len(checks), 3)
    return {"score": score, **checks}


@weave.op()
def continual_learning_score(
    output: dict[str, Any],
    phase: str,
    target_memory_terms: list[str],
) -> dict[str, Any]:
    if phase != "after_reflection":
        return {"score": 1.0, "reason": "baseline row does not require reflection memory"}

    answer = str(output.get("answer", ""))
    retrieved = output.get("retrieved_context", [])
    coverage, matched = _term_coverage(answer, target_memory_terms)
    retrieved_reflection = any(item.get("collection") == "ai_reflections" for item in retrieved)
    score = round((0.7 * coverage) + (0.3 if retrieved_reflection else 0.0), 3)
    return {
        "score": min(score, 1.0),
        "matched_memory_terms": matched,
        "retrieved_reflection": retrieved_reflection,
    }


@weave.op()
def grounded_context_score(
    output: dict[str, Any],
    expected_collections: list[str],
    min_context_count: int,
) -> dict[str, Any]:
    retrieved = output.get("retrieved_context", [])
    collections = [item.get("collection") for item in retrieved]
    expected_hits = [name for name in expected_collections if name in collections]
    enough_context = len(retrieved) >= min_context_count
    # Expected collections are acceptable source types, not a requirement to hit
    # every collection on every row. A grounded answer needs enough retrieved
    # context and at least one relevant platform source.
    collection_score = 1.0 if expected_hits else 0.0
    context_score = 1.0 if enough_context else (len(retrieved) / max(min_context_count, 1))
    score = round((0.65 * collection_score) + (0.35 * context_score), 3)
    return {
        "score": min(score, 1.0),
        "retrieved_count": len(retrieved),
        "retrieved_collections": collections,
        "matched_expected_collections": expected_hits,
    }


@weave.op()
def no_weight_finetuning_claim_score(
    output: dict[str, Any],
    forbidden_claims: list[str],
) -> dict[str, Any]:
    answer = str(output.get("answer", ""))
    lower = answer.lower()
    matched_forbidden = [claim for claim in forbidden_claims if claim.lower() in lower]
    return {
        "score": 0.0 if matched_forbidden else 1.0,
        "matched_forbidden_claims": matched_forbidden,
    }


@weave.op()
async def gemini_judge_score(
    output: dict[str, Any],
    question: str,
    phase: str,
) -> dict[str, Any]:
    """Optional LLM judge for demo readability in Weave."""
    ctx = _context()
    if not ctx.gemini.client:
        return {"score": 0.5, "reason": "Gemini judge unavailable; mock fallback"}

    prompt = f"""
You are judging a tutoring answer for TutorLoop.
Return strict JSON with keys: score, reason.
Score from 0.0 to 1.0.

Criteria:
- The answer teaches clearly.
- It includes a worked example or concrete analogy.
- It asks a short check question.
- If phase is after_reflection, it uses prior tutoring memory or weak-topic context.
- It must not claim model weights were fine-tuned or changed.

Phase: {phase}
Student question: {question}
Answer:
{output.get("answer", "")}
"""
    try:
        response = await asyncio.to_thread(
            ctx.gemini.client.models.generate_content,
            model=ctx.gemini.settings.gemini_model,
            contents=prompt,
        )
        match = re.search(r"\{.*\}", response.text or "", re.DOTALL)
        if not match:
            raise ValueError("Gemini judge did not return JSON")
        parsed = json.loads(match.group(0))
        score = max(0.0, min(1.0, float(parsed.get("score", 0.0))))
        return {"score": round(score, 3), "reason": str(parsed.get("reason", ""))}
    except Exception as exc:  # noqa: BLE001 - eval should continue if judge parsing fails.
        return {"score": 0.0, "reason": f"judge_error:{exc.__class__.__name__}"}


async def run_eval(args: argparse.Namespace) -> dict[str, Any]:
    global EVAL_CONTEXT

    settings = get_settings().model_copy(update={"mongodb_allow_vector_fallback": True})
    status = init_weave(settings)
    if not status.startswith("enabled:"):
        raise SystemExit(
            "Weave is not enabled. Set WEAVE_ENABLED=true and WANDB_API_KEY in .env, "
            f"then retry. Current status: {get_weave_status()}"
        )

    db = AppDatabase(settings)
    await db.connect()
    gemini = GeminiService(settings)
    vector_search = VectorSearchService(db, gemini, settings)
    EVAL_CONTEXT = EvalContext(db=db, gemini=gemini, vector_search=vector_search)

    rows = EVAL_ROWS[: args.limit] if args.limit else EVAL_ROWS
    scorers = [
        expected_terms_score,
        pedagogy_score,
        continual_learning_score,
        grounded_context_score,
        no_weight_finetuning_claim_score,
    ]
    if args.llm_judge:
        scorers.append(gemini_judge_score)

    try:
        evaluation = weave.Evaluation(
            name=args.name,
            description=(
                "TutorLoop continual-learning eval: baseline AI tutor answers versus "
                "answers with human tutoring reflection memory."
            ),
            dataset=rows,
            scorers=scorers,
            trials=args.trials,
            metadata={
                "app": "TutorLoop",
                "theme": "continual learning",
                "weave_status": get_weave_status(),
                "uses_model_weight_finetuning": False,
                "retrieval_collections": AI_RETRIEVAL_COLLECTIONS,
            },
        )
        summary = await evaluation.evaluate(tutorloop_ai_tutor_eval)
        return summary
    finally:
        await db.close()
        EVAL_CONTEXT = None


def main() -> None:
    parser = argparse.ArgumentParser(description="Run TutorLoop W&B Weave evaluations.")
    parser.add_argument("--name", default="tutorloop-continual-learning-eval", help="Weave evaluation name")
    parser.add_argument("--limit", type=int, default=0, help="Limit number of eval rows for smoke tests")
    parser.add_argument("--trials", type=int, default=1, help="Number of trials per eval row")
    parser.add_argument("--llm-judge", action="store_true", help="Add a Gemini judge scorer")
    args = parser.parse_args()

    summary = asyncio.run(run_eval(args))
    print(json.dumps(summary, indent=2, default=str))


if __name__ == "__main__":
    main()
