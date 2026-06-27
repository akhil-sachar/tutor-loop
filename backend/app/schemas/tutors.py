from pydantic import BaseModel, Field


class TutorOut(BaseModel):
    id: str = Field(alias="_id")
    user_id: str
    display_name: str
    subjects: list[str]
    bio: str
    hourly_rate: float
    rating: float
    teaching_style: str
    score: float | None = None
    reason: str | None = None

    model_config = {"populate_by_name": True}
