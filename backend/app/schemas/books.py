from pydantic import BaseModel


class BookOut(BaseModel):
    id: str
    title: str
    subject: str
    description: str
    price: float
    rating: float
    author: str | None = None


class BookAccessRequest(BaseModel):
    student_id: str
