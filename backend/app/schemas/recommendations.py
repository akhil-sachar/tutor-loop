from pydantic import BaseModel, Field


class RecommendationOut(BaseModel):
    id: str = Field(alias="_id")
    student_id: str
    type: str
    target_id: str
    title: str
    subject: str | None = None
    reason: str
    score: float
    metadata: dict = {}

    model_config = {"populate_by_name": True}
