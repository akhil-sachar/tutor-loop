from pydantic import BaseModel, Field


class TutorOut(BaseModel):
    id: str = Field(alias="_id")
    user_id: str
    display_name: str
    subjects: list[str]
    bio: str
    about_me: str | None = None
    major_topics: list[str] = Field(default_factory=list)
    credentials: str | None = None
    study_experience: str | None = None
    work_experience: str | None = None
    hourly_rate: float
    rating: float
    teaching_style: str
    score: float | None = None
    reason: str | None = None

    model_config = {"populate_by_name": True}
