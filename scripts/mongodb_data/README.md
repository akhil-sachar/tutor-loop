# TutorLoop MongoDB upload data

JSON exports for seeding MongoDB Atlas. Regenerate anytime with:

```bash
python scripts/generate_mongodb_data.py
```

## Files

| File | Contents |
|------|----------|
| `users.json` | Demo student and tutor accounts |
| `tutors.json` | Searchable tutor profiles with embeddings |
| `notes.json` | Marketplace notes with embeddings |
| `books.json` | Platform textbook catalog |
| `book_chunks.json` | PDF chunks for AI tutor retrieval |
| `purchases.json` | Sample note purchase |
| `bookings.json` / `sessions.json` | Demo tutoring booking |
| `transcripts.json` | Human + AI session transcripts |
| `ai_conversations.json` | Sample AI tutor chat |
| `ai_reflections.json` | Human and AI reflection artifacts |
| `student_learning_profiles.json` | Continual-learning memory |
| `recommendations.json` | Personalized recommendations |
| `reviews.json` | Tutor and note reviews |
| `manifest.json` | Collection counts and generation time |

## Import

**Python (recommended):**

```bash
python scripts/generate_mongodb_data.py --upload --reset
```

**PowerShell + mongoimport:**

```powershell
$env:MONGODB_URI = "mongodb+srv://user:pass@cluster.mongodb.net/tutorloop"
.\scripts\import_mongodb_data.ps1
```

**mongosh:**

```bash
mongosh "<uri>/tutorloop" scripts/import_mongodb_data.js
```

After import, vector search indexes are created via `scripts/mongodb_atlas_indexes.js`.

## Options

- `--chunks-per-book 12` — limit book chunks per title (default)
- `--full-books` — export all ingested PDF chunks (large)
- `--upload --reset` — push directly to `MONGODB_URI` from `.env`

Demo login after import: `student@tutorloop.demo` / `password123`
