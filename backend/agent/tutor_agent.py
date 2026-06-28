"""
TutorLoop LiveKit voice agent.

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
from livekit.agents import Agent, AgentServer, AgentSession, JobContext, room_io
from livekit.plugins import google

AGENT_NAME = "tutorloop-ai-tutor"
DEFAULT_GEMINI_LIVE_MODEL = "gemini-2.5-flash-native-audio-latest"


def _build_instructions(metadata: dict) -> str:
    subject = metadata.get("subject", "math")
    topic = metadata.get("topic", "the current lesson")
    notes = metadata.get("lecture_notes", [])
    outline = metadata.get("lecture_outline", [])
    weak = metadata.get("weak_topics", [])
    guidance = metadata.get("future_ai_instructions", [])

    notes_text = "\n".join(f"- {note.get('title')}: {note.get('snippet')}" for note in notes[:8]) or "- Use general tutoring knowledge."
    outline_text = "\n".join(f"{index + 1}. {step}" for index, step in enumerate(outline)) or "1. Explain\n2. Example\n3. Check understanding"

    return f"""You are TutorLoop's virtual AI tutor delivering a live voice lecture on {subject}: {topic}.

Follow this lecture outline:
{outline_text}

Visible notes and textbook excerpts for the student:
{notes_text}

Student weak topics: {", ".join(weak) or "not recorded yet"}
Prior tutoring guidance: {" ".join(guidance[:5])}

Behavior:
- Deliver a full lecture in clear spoken segments.
- The student can interrupt with voice questions at any time — pause, answer, then continue.
- Ground explanations in the notes above when relevant.
- Use a warm, Socratic tutoring tone.
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
    live_model = os.getenv("GEMINI_LIVE_MODEL", DEFAULT_GEMINI_LIVE_MODEL)

    session = AgentSession(
        llm=google.realtime.RealtimeModel(
            model=live_model,
            voice="Puck",
            instructions=instructions,
            api_key=api_key,
        )
    )

    await session.start(
        room=ctx.room,
        agent=TutorLoopLectureAgent(instructions=instructions),
        room_options=room_io.RoomOptions(video_input=True),
    )

    topic = metadata.get("topic", "today's topic")
    await session.generate_reply(
        instructions=(
            f"Begin the live lecture on {topic}. Greet the student, tell them they can "
            "speak anytime to interject with questions, then start step 1 of the outline."
        )
    )


if __name__ == "__main__":
    agents.cli.run_app(server)
