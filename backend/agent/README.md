# TutorLoop LiveKit AI tutor agent

Voice lecture agent using **Gemini 3.5** (STT → LLM → TTS pipeline), not the Gemini Live API.
The same `GEMINI_MODEL` powers text chat (`/ai/chat`) and live voice tutoring.

This agent is **started automatically** when you run:

```bash
python run.py
```

## Requirements

Set in `.env`:

```bash
GEMINI_API_KEY=...          # also used as GOOGLE_API_KEY for the agent
GEMINI_MODEL=gemini-3.5-flash
GEMINI_TTS_MODEL=gemini-2.5-flash-preview-tts
LIVEKIT_URL=wss://...
LIVEKIT_API_KEY=...
LIVEKIT_API_SECRET=...
RUN_LIVEKIT_AGENT=true
```

Speech-to-text uses LiveKit Inference (`TUTOR_STT_MODEL=deepgram/nova-3` by default), billed through LiveKit Cloud.

Agent dispatch name: `tutorloop-ai-tutor`

## Manual run (optional)

```bash
python -m backend.agent.tutor_agent dev
```

## First-time setup

After installing dependencies:

```bash
python -m livekit.agents download-files
```
