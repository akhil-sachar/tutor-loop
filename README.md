# TutorLoop

Human tutoring that teaches the AI tutor to get better.

TutorLoop is a hackathon MVP for an education marketplace where students buy tutor notes and platform books, book live tutoring, join an AI tutor grounded in textbook content, and receive recommendations that improve after human and AI tutoring sessions. The continual-learning loop uses memory, embeddings, retrieved context, reflections, and prompt instructions. It does not fine-tune model weights.

## Stack

- Backend: FastAPI
- Database: MongoDB Atlas, with in-memory fallback for demos
- Semantic search: MongoDB Atlas Vector Search, with local fallback scoring
- AI: Gemini for tutor chat, embeddings, summaries, quiz/reflection generation
- Observability: Weights & Biases Weave tracing for AI tutor, reflection, quiz, and lecture flows
- Live classroom: LiveKit token generation, with mock tokens when credentials are missing
- Frontend: static HTML/CSS/JS served by FastAPI
- Deployment: Docker-ready for DigitalOcean App Platform

## Quickstart

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r backend/requirements.txt
copy .env.example .env
python run.py
```

Open `http://127.0.0.1:8080`.

**One command** starts everything:
- FastAPI web app + frontend
- LiveKit AI lecture agent (voice + video tutoring)

Set `GEMINI_API_KEY`, `LIVEKIT_URL`, `LIVEKIT_API_KEY`, and `LIVEKIT_API_SECRET` in `.env` for full voice AI lectures. On first install, optionally run:

```bash
python -m livekit.agents download-files
```

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
7. Ask the AI tutor about derivatives again (retrieval includes platform books and past reflections)
8. Reflect on the AI tutor session to update the learning profile further
9. Recommendations refresh from the updated profile and reflection vectors

## Main API Endpoints

- `POST /auth/register`
- `POST /auth/login`
- `GET /notes/search`
- `POST /notes`
- `POST /notes/{note_id}/purchase`
- `GET /tutors/search`
- `GET /books`
- `GET /books/search`
- `POST /books/{book_id}/access`
- `POST /bookings`
- `GET /bookings/{booking_id}`
- `POST /livekit/token`
- `POST /ai/lecture/start`
- `POST /ai/lecture/{lecture_id}/complete`
- `POST /ai/chat`
- `POST /ai/conversations/{conversation_id}/reflect`
- `POST /sessions/{session_id}/reflect`
- `GET /students/{student_id}/recommendations`
- `GET /search`

## MongoDB Atlas Setup

1. Create an Atlas cluster and database named `tutorloop`.
2. Set `MONGODB_URI` in `.env`.
3. Import the bundled demo dataset (recommended):

```bash
python scripts/generate_mongodb_data.py
python scripts/generate_mongodb_data.py --upload --reset
```

Or use MongoDB tools:

```powershell
$env:MONGODB_URI = "mongodb+srv://..."
.\scripts\import_mongodb_data.ps1
```

Or with `mongosh`:

```bash
python scripts/generate_mongodb_data.py
mongosh "<your-uri>/tutorloop" scripts/import_mongodb_data.js
```

4. Run `scripts/mongodb_atlas_indexes.js` in Atlas/`mongosh`, or `python scripts/create_vector_indexes.py`, to create the vector indexes if they were not created by the import script.
5. Each collection has its own distinct vector index (`notes_vector_index`, `books_vector_index`, `book_chunks_vector_index`, `tutors_vector_index`, etc.), each declaring only the filter fields that collection uses. `MONGODB_VECTOR_INDEX` is only a fallback name for any collection not in that map.

### Generate upload data

`scripts/generate_mongodb_data.py` builds a full TutorLoop dataset with:

- demo users, tutors, notes, bookings, and sessions
- platform books and searchable `book_chunks` from `backend/app/content/*.pdf`
- human and AI session reflections, purchases, reviews, and recommendations
- 768-dimension embeddings (mock vectors when `GEMINI_API_KEY` is missing)

Options:

```bash
python scripts/generate_mongodb_data.py                  # export JSON to scripts/mongodb_data/
python scripts/generate_mongodb_data.py --full-books     # export every PDF chunk
python scripts/generate_mongodb_data.py --upload --reset # push JSON to Atlas
```

Exported files live in `scripts/mongodb_data/` (`manifest.json` lists collection counts).

Collections used:

- `users`
- `tutors`
- `notes`
- `books`
- `book_chunks`
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
WEAVE_ENABLED=false
WEAVE_PROJECT=tutorloop
WEAVE_ENTITY=
WEAVE_TRACE_EMBEDDINGS=false
WANDB_API_KEY=...
```

If your Gemini account exposes a different model name, update `GEMINI_MODEL` without changing application code.
Set `WEAVE_ENABLED=true` after adding `WANDB_API_KEY` or logging in with `wandb login`. Embedding traces are off by default because they can create a high volume of trace events during semantic search and data seeding.

## Run options

```bash
python run.py                  # dev: API reload + LiveKit agent
python run.py --port 8000      # custom port
python run.py --no-agent       # API only
python run.py --production     # Docker / production (no reload)
```

Set `RUN_LIVEKIT_AGENT=false` in `.env` to skip the voice agent.

## W&B Weave Evaluations

Run the continual-learning eval after setting `WEAVE_ENABLED=true` and `WANDB_API_KEY`:

```bash
python scripts/run_weave_evals.py
```

For a quick smoke run:

```bash
python scripts/run_weave_evals.py --limit 1
```

The eval compares baseline AI tutor answers against answers that include synthetic human-session reflection memory. Weave records the model output, retrieved context, and scorer results for expected concept coverage, tutoring structure, grounded retrieval context, continual-learning memory use, and avoiding any claim that model weights were fine-tuned. Add `--llm-judge` to include a Gemini judge scorer.

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

- purchased notes and platform books
- tutor profiles and teaching styles
- AI conversations (embedded and reflectable)
- human session transcripts
- AI and human session summaries
- student weaknesses
- successful teaching methods
- future AI tutoring instructions
- recommendation vectors

The reflection endpoints write an `ai_reflections` document and update `student_learning_profiles` for both human tutoring sessions (`POST /sessions/{session_id}/reflect`) and AI tutor sessions (`POST /ai/conversations/{conversation_id}/reflect`). Platform PDFs under `backend/app/content/` are ingested at startup into `books` and `book_chunks` for retrieval during AI tutoring.
