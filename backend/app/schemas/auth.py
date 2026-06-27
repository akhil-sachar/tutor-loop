from pydantic import BaseModel, Field

from backend.app.models.enums import UserRole


class RegisterRequest(BaseModel):
    name: str = Field(..., min_length=2)
    email: str
    password: str = Field(..., min_length=6)
    role: UserRole = UserRole.student
    subjects: list[str] = []
    bio: str | None = None


class LoginRequest(BaseModel):
    email: str
    password: str


class UserOut(BaseModel):
    id: str = Field(alias="_id")
    name: str
    email: str
    role: UserRole
    subjects: list[str] = []
    bio: str | None = None

    model_config = {"populate_by_name": True}


class AuthResponse(BaseModel):
    token: str
    user: UserOut
    is_mock_auth: bool = True
