"""
TutorLoop LiveKit voice agent.

Uses an STT -> Gemini 3.5 -> TTS pipeline (not the Gemini Live API) so the same
model family powers text chat and live voice tutoring.

Started automatically by `python run.py` alongside the FastAPI app.
Manual run: python -m backend.agent.tutor_agent dev
"""

from __future__ import annotations

import json
import os
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[2]
load_dotenv(ROOT / ".env")
load_dotenv(ROOT / "backend" / ".env")

from livekit import agents
from livekit.agents import Agent, AgentServer, AgentSession, JobContext, TurnHandlingOptions, inference, room_io
from livekit.plugins import google

try:
    from livekit.plugins import ai_coustics
except Exception:  # Optional plugin; app still runs without it.
    ai_coustics = None

AGENT_NAME = "tutorloop-ai-tutor"
DEFAULT_GEMINI_MODEL = "gemini-3.5-flash"
DEFAULT_GEMINI_TTS_MODEL = "gemini-2.5-flash-preview-tts"
DEFAULT_STT_MODEL = "deepgram/nova-3"


def _build_instructions(metadata: dict) -> str:
    subject = metadata.get("subject", "math")
    topic = metadata.get("topic", "the current lesson")
    notes = metadata.get("lecture_notes", [])
    outline = metadata.get("lecture_outline", [])
    weak = metadata.get("weak_topics", [])
    guidance = metadata.get("future_ai_instructions", [])
    grounded = bool(metadata.get("grounded_sources"))

    notes_text = "\n".join(f"- {note.get('title')}: {note.get('snippet')}" for note in notes[:8]) or "- Use general tutoring knowledge."
    outline_text = "\n".join(f"{index + 1}. {step}" for index, step in enumerate(outline)) or "1. Explain\n2. Example\n3. Check understanding"

    grounding_rule = (
        "- The student selected the specific sources above. Base the lecture PRIMARILY on "
        "these materials, cite them by title, and say so if a question goes beyond them."
        if grounded
        else "- Ground explanations in the notes above when relevant."
    )

    return f"""You are TutorLoop's virtual AI tutor delivering a live voice lecture on {subject}: {topic}.

Follow this lecture outline:
{outline_text}

Visible notes and textbook excerpts for the student{" (student-selected sources)" if grounded else ""}:
{notes_text}

Student weak topics: {", ".join(weak) or "not recorded yet"}
Prior tutoring guidance: {" ".join(guidance[:5])}

Behavior:
- Begin immediately by greeting the student and telling them they can speak anytime to ask questions.
- Deliver the full lecture following the outline above in clear spoken segments.
- The student can interrupt with voice questions at any time — pause, answer, then continue.
- Ignore ambient/background noise (keyboard clicks, fans, room chatter) unless the student is clearly speaking to you.
{grounding_rule}
- Use a warm, Socratic tutoring tone.
- Keep spoken responses concise and natural for text-to-speech: no markdown, bullets, emojis, or asterisks.
- Never claim model weights were fine-tuned; you improve through memory and reflection."""


class TutorLoopLectureAgent(Agent):
    def __init__(self, instructions: str) -> None:
        super().__init__(instructions=instructions)


server = AgentServer()


@server.rtc_session(agent_name=AGENT_NAME)
async def tutorloop_ai_tutor(ctx: JobContext) -> None:
    metadata = json.loads(ctx.job.metadata or "{}")
    instructions = _build_instructions(metadata)
    api_key = os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY")
    gemini_model = os.getenv("GEMINI_MODEL", DEFAULT_GEMINI_MODEL)
    gemini_tts_model = os.getenv("GEMINI_TTS_MODEL", DEFAULT_GEMINI_TTS_MODEL)
    stt_model = os.getenv("TUTOR_STT_MODEL", DEFAULT_STT_MODEL)

    session = AgentSession(
        # STT via LiveKit Inference (uses LIVEKIT_* keys). Gemini has no streaming STT API.
        stt=inference.STT(model=stt_model, language="en"),
        # Standard Gemini generateContent — same model family as /ai/chat.
        llm=google.LLM(
            model=gemini_model,
            api_key=api_key,
        ),
        # Gemini TTS (uses GOOGLE_API_KEY / GEMINI_API_KEY).
        tts=google.beta.GeminiTTS(
            model=gemini_tts_model,
            voice_name=os.getenv("GEMINI_TTS_VOICE", "Zephyr"),
            instructions="Speak warmly and clearly like a patient tutor lecturing a student.",
            api_key=api_key,
        ),
        turn_handling=TurnHandlingOptions(
            turn_detection=inference.TurnDetector(
                unlikely_threshold=0.68,
                backchannel_threshold=0.75,
            ),
            interruption={
                "enabled": True,
                "mode": "adaptive",
                "min_duration": 0.9,
                "min_words": 3,
                "discard_audio_if_uninterruptible": True,
                "resume_false_interruption": True,
                "false_interruption_timeout": 1.2,
            },
            endpointing={
                "mode": "dynamic",
                "min_delay": 0.45,
                "max_delay": 1.6,
                "alpha": 0.65,
            },
        ),
    )

    room_options = room_io.RoomOptions(video_input=True)
    if ai_coustics:
        room_options = room_io.RoomOptions(
            video_input=True,
            audio_input=room_io.AudioInputOptions(
                noise_cancellation=ai_coustics.audio_enhancement(model=ai_coustics.EnhancerModel.QUAIL_VF_S),
            ),
        )

    await session.start(
        room=ctx.room,
        agent=TutorLoopLectureAgent(instructions=instructions),
        room_options=room_options,
    )

    subject = metadata.get("subject", "this subject")
    topic = metadata.get("topic", "today's topic")
    try:
        await session.generate_reply(
            instructions=(
                f"Begin the live lecture on {subject}: {topic}. Greet the student warmly, "
                "tell them they can speak anytime to interject with questions, then teach "
                "step 1 of the outline. Keep going through the outline, pausing for questions."
            )
        )
    except Exception as exc:  # noqa: BLE001 - keep the session alive if kickoff fails
        print(f"[tutorloop-agent] initial generate_reply failed: {exc}")


if __name__ == "__main__":
    agents.cli.run_app(server)
