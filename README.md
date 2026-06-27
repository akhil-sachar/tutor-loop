# TutorLoop

Human tutoring that teaches the AI tutor to get better.

TutorLoop is a hackathon MVP for an education marketplace where students buy tutor notes, book live tutoring, join an AI tutor, and receive recommendations that improve after human tutoring sessions. The continual-learning loop uses memory, embeddings, retrieved context, reflections, and prompt instructions. It does not fine-tune model weights.

## Stack

- Backend: FastAPI
- Database: MongoDB Atlas, with in-memory fallback for demos
- Semantic search: MongoDB Atlas Vector Search, with local fallback scoring
- AI: Gemini for tutor chat, embeddings, summaries, quiz/reflection generation
- Live classroom: LiveKit token generation, with mock tokens when credentials are missing
- Frontend: static HTML/CSS/JS served by FastAPI
- Deployment: Docker-ready for DigitalOcean App Platform

## Quickstart

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r backend/requirements.txt
copy .env.example .env
uvicorn backend.app.main:app --reload --host 127.0.0.1 --port 8000
```

Open `http://127.0.0.1:8000`.

The app runs without cloud credentials. Missing MongoDB, Gemini, and LiveKit keys automatically trigger mock fallbacks so the demo flow still works.

Demo login:

- Student: `student@tutorloop.demo`
- Tutor: `tutor@tutorloop.demo`
- Password: `password123`

## Demo Flow

1. Search: `I'm confused about derivatives`
2. `/search`, `/notes/search`, and `/tutors/search` return semantic matches
3. Buy the derivative notes or book Elena Rivera
4. Join the mock LiveKit classroom
5. Reflect on the session transcript and choose a translation language
6. The student learning profile updates with weak topics and teaching methods
7. Ask the AI tutor about derivatives again
8. Recommendations refresh from the updated profile and reflection vectors

## Main API Endpoints

- `POST /auth/register`
- `POST /auth/login`
- `GET /notes/search`
- `POST /notes`
- `POST /notes/{note_id}/purchase`
- `GET /tutors/search`
- `POST /bookings`
- `GET /bookings/{booking_id}`
- `POST /livekit/token`
- `POST /ai/chat`
- `POST /sessions/{session_id}/reflect`
- `GET /students/{student_id}/recommendations`
- `GET /search`

## MongoDB Atlas Setup

1. Create an Atlas cluster and database named `tutorloop`.
2. Set `MONGODB_URI` in `.env`.
3. Run `scripts/mongodb_atlas_indexes.js` in Atlas or `mongosh`.
4. Keep `MONGODB_VECTOR_INDEX=tutorloop_vector_index`.

Collections used:

- `users`
- `tutors`
- `notes`
- `purchases`
- `bookings`
- `sessions`
- `transcripts`
- `ai_conversations`
- `ai_reflections`
- `student_learning_profiles`
- `recommendations`
- `reviews`

## Provider Keys

Set these in `.env` or DigitalOcean App Platform:

```bash
MONGODB_URI=...
GEMINI_API_KEY=...
GEMINI_MODEL=gemini-3.5-pro
GEMINI_EMBEDDING_MODEL=gemini-embedding-001
LIVEKIT_URL=...
LIVEKIT_API_KEY=...
LIVEKIT_API_SECRET=...
```

If your Gemini account exposes a different model name, update `GEMINI_MODEL` without changing application code.

## Seed Data

The app seeds demo data at startup when `DEMO_SEED_ON_STARTUP=true`.

Manual reset:

```bash
python -m backend.app.seed
```

Or call:

```bash
curl -X POST http://127.0.0.1:8000/demo/seed
```

## DigitalOcean Deployment

The included `Dockerfile` runs the FastAPI app and serves the frontend on port `8080`.

For App Platform:

1. Push the repo to GitHub.
2. Update `.do/app.yaml` with your repo name.
3. Add runtime secrets for `MONGODB_URI`, `GEMINI_API_KEY`, and LiveKit keys.
4. Create the app from `.do/app.yaml`.

For a Droplet:

```bash
docker build -t tutorloop .
docker run -p 8080:8080 --env-file .env tutorloop
```

## Continual Learning Design

TutorLoop improves the AI tutor by storing and retrieving:

- purchased notes
- tutor profiles and teaching styles
- AI conversations
- human session transcripts
- session summaries
- student weaknesses
- successful teaching methods
- future AI tutoring instructions
- recommendation vectors

The reflection endpoint writes an `ai_reflections` document and updates `student_learning_profiles`. Later AI chat calls retrieve those memories through vector search and include them in the Gemini prompt.
