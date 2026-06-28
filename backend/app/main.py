from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from backend.app.api.routes import ai, auth, bookings, books, demo, livekit, notes, recommendations, search, sessions, tutors
from backend.app.core.config import get_settings
from backend.app.db.mongo import AppDatabase
from backend.app.seed import seed_demo_data
from backend.app.services.book_service import BookService
from backend.app.services.gemini_service import GeminiService
from backend.app.services.learning_service import LearningSignalService
from backend.app.services.livekit_service import LiveKitService
from backend.app.services.recommendation_service import RecommendationService
from backend.app.services.reflection_service import ReflectionService
from backend.app.services.vector_search import VectorSearchService


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    db = AppDatabase(settings)
    await db.connect()

    gemini = GeminiService(settings)
    vector_search = VectorSearchService(db, gemini, settings)
    livekit = LiveKitService(settings)
    recommendations_service = RecommendationService(db, vector_search, gemini)
    reflections = ReflectionService(db, gemini, vector_search, recommendations_service)
    books_service = BookService(db, vector_search)
    learning = LearningSignalService(db, gemini, recommendations_service)

    app.state.settings = settings
    app.state.db = db
    app.state.gemini = gemini
    app.state.vector_search = vector_search
    app.state.livekit = livekit
    app.state.recommendations = recommendations_service
    app.state.reflections = reflections
    app.state.books = books_service
    app.state.learning = learning

    if settings.demo_seed_on_startup:
        await seed_demo_data(db, gemini, vector_search, reset=False)
        await books_service.ensure_books_ingested()
        await recommendations_service.refresh_for_student("student-demo-maya")

    yield
    await db.close()


settings = get_settings()
app = FastAPI(
    title="TutorLoop API",
    description="Human tutoring that teaches the AI tutor to get better.",
    version="0.1.0",
    lifespan=lifespan,
)

origins = ["*"] if settings.cors_origins == "*" else [origin.strip() for origin in settings.cors_origins.split(",")]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health", tags=["health"])
async def health():
    settings = get_settings()
    agent_ready = settings.use_livekit and settings.use_gemini
    db = app.state.db
    return {
        "status": "ok",
        "app": settings.app_name,
        "mongo": "atlas" if db.is_mongo else "memory",
        "mongo_error": db.connection_error,
        "gemini": "configured" if settings.use_gemini else "mock",
        "livekit": "configured" if settings.use_livekit else "mock",
        "ai_lecture_agent": "enabled" if agent_ready else "browser_fallback",
        "run_command": "python run.py",
    }


app.include_router(auth.router)
app.include_router(notes.router)
app.include_router(books.router)
app.include_router(tutors.router)
app.include_router(bookings.router)
app.include_router(livekit.router)
app.include_router(ai.router)
app.include_router(sessions.router)
app.include_router(recommendations.router)
app.include_router(search.router)
app.include_router(demo.router)


if settings.frontend_dir.exists():
    app.mount("/assets", StaticFiles(directory=settings.frontend_dir), name="assets")


@app.get("/", include_in_schema=False)
async def frontend_root():
    return FileResponse(settings.frontend_dir / "index.html")


@app.get("/{page_name}.html", include_in_schema=False)
async def frontend_page(page_name: str):
    path = settings.frontend_dir / f"{page_name}.html"
    if path.exists():
        return FileResponse(path)
    return FileResponse(settings.frontend_dir / "index.html")
