from fastapi import APIRouter, Depends, HTTPException, status

from backend.app.api.deps import get_db
from backend.app.core.config import get_settings
from backend.app.core.security import hash_password, make_demo_token, verify_password
from backend.app.schemas.auth import AuthResponse, LoginRequest, RegisterRequest

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=AuthResponse)
async def register(payload: RegisterRequest, db=Depends(get_db)):
    existing = await db.find_one("users", {"email": payload.email.lower()})
    if existing:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email is already registered")

    user = {
        "name": payload.name,
        "email": payload.email.lower(),
        "password_hash": hash_password(payload.password),
        "role": payload.role,
        "subjects": payload.subjects,
        "bio": payload.bio,
    }
    user_id = await db.insert_one("users", user)
    user["_id"] = user_id

    if payload.role == "tutor":
        await db.insert_one(
            "tutors",
            {
                "user_id": user_id,
                "display_name": payload.name,
                "subjects": payload.subjects,
                "bio": payload.bio or "New TutorLoop tutor",
                "hourly_rate": 35,
                "rating": 4.5,
                "teaching_style": "Personalized tutoring",
                "content_type": "tutor_profile",
            },
        )

    settings = get_settings()
    return {"token": make_demo_token(user_id, settings.jwt_secret), "user": user, "is_mock_auth": True}


@router.post("/login", response_model=AuthResponse)
async def login(payload: LoginRequest, db=Depends(get_db)):
    user = await db.find_one("users", {"email": payload.email.lower()})
    if not user or not verify_password(payload.password, user.get("password_hash", "")):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

    settings = get_settings()
    return {"token": make_demo_token(user["_id"], settings.jwt_secret), "user": user, "is_mock_auth": True}
