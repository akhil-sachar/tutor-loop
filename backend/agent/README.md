# TutorLoop LiveKit AI tutor agent

Voice + video lecture agent using Gemini Live API.

This agent is **started automatically** when you run:

```bash
python run.py
```

## Requirements

Set in `.env`:

```bash
GEMINI_API_KEY=...          # also used as GOOGLE_API_KEY for the agent
LIVEKIT_URL=wss://...
LIVEKIT_API_KEY=...
LIVEKIT_API_SECRET=...
RUN_LIVEKIT_AGENT=true
```

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
