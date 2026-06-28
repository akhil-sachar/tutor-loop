from pydantic import BaseModel, Field


class QuizStartRequest(BaseModel):
    student_id: str
    subject: str
    topic: str
    num_questions: int = Field(default=3, ge=1, le=6)


class QuizQuestionOut(BaseModel):
    id: str
    question: str


class QuizStartResponse(BaseModel):
    quiz_id: str
    subject: str
    topic: str
    questions: list[QuizQuestionOut]
    prior_mastery: float
    is_mock: bool


class QuizAnswer(BaseModel):
    question_id: str
    answer: str


class QuizGradeRequest(BaseModel):
    quiz_id: str
    answers: list[QuizAnswer]


class QuizQuestionResult(BaseModel):
    question: str
    score: float
    correct: bool
    feedback: str


class QuizGradeResponse(BaseModel):
    quiz_id: str
    subject: str
    topic: str
    score: float
    prior_mastery: float
    new_mastery: float
    delta: float
    mastered: bool
    per_question: list[QuizQuestionResult]
    weak_topics: list[str]
    mastered_topics: list[str]
    is_mock: bool


class ConversationFeedbackRequest(BaseModel):
    student_id: str
    helpful: bool
    note: str | None = None


class ConversationFeedbackResponse(BaseModel):
    conversation_id: str
    helpful: bool
    reward: float
    message: str
