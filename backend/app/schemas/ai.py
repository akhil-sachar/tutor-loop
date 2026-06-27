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


class AIReflectRequest(BaseModel):
    target_language: str = "English"


class AIChatResponse(BaseModel):
    conversation_id: str
    answer: str
    retrieved_context: list[RetrievedContext]
    is_mock: bool


class AIReflectResponse(BaseModel):
    reflection_id: str
    conversation_id: str | None = None
    session_id: str | None = None
    student_id: str
    source: str
    summary: str
    translated_summary: str
    weaknesses: list[str]
    successful_teaching_methods: list[str]
    future_ai_instructions: list[str]
    updated_profile: dict
    is_mock: bool


class LectureNote(BaseModel):
    id: str
    title: str
    subject: str | None = None
    snippet: str
    source: str


class AILectureStartRequest(BaseModel):
    student_id: str
    subject: str = "Calculus"
    topic: str = "derivatives and tangent slope intuition"
    language: str = "English"


class AILectureStartResponse(BaseModel):
    lecture_id: str
    room_id: str
    room_url: str
    token: str
    is_mock: bool
    agent_name: str | None = None
    notes: list[LectureNote]
    lecture_outline: list[str]


class AILectureCompleteRequest(BaseModel):
    transcript: str
    student_id: str


class AILectureCompleteResponse(BaseModel):
    lecture_id: str
    conversation_id: str
    message: str
