from pydantic import BaseModel


class ReflectRequest(BaseModel):
    transcript: str | None = None
    target_language: str = "English"


class ReflectionOut(BaseModel):
    reflection_id: str
    session_id: str | None = None
    conversation_id: str | None = None
    student_id: str
    source: str = "human"
    summary: str
    translated_summary: str
    weaknesses: list[str]
    successful_teaching_methods: list[str]
    future_ai_instructions: list[str]
    updated_profile: dict
    is_mock: bool
