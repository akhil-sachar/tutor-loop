from pydantic import BaseModel


class AIChatRequest(BaseModel):
    student_id: str
    question: str
    subject: str | None = None
    language: str = "English"


class RetrievedContext(BaseModel):
    id: str
    collection: str
    title: str
    score: float
    content_type: str


class AIChatResponse(BaseModel):
    conversation_id: str
    answer: str
    retrieved_context: list[RetrievedContext]
    is_mock: bool
