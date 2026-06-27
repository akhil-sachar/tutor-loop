from datetime import datetime

from pydantic import BaseModel, Field


class BookingCreate(BaseModel):
    tutor_id: str
    student_id: str
    subject: str
    starts_at: datetime
    duration_minutes: int = Field(default=45, ge=15, le=180)


class BookingOut(BaseModel):
    id: str = Field(alias="_id")
    tutor_id: str
    student_id: str
    subject: str
    starts_at: datetime
    duration_minutes: int
    status: str
    room_id: str
    session_id: str | None = None

    model_config = {"populate_by_name": True}


class LiveKitTokenRequest(BaseModel):
    booking_id: str
    user_id: str
    display_name: str | None = None


class LiveKitTokenOut(BaseModel):
    room_id: str
    room_url: str
    token: str
    is_mock: bool
