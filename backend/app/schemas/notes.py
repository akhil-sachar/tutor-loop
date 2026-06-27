from pydantic import BaseModel, Field


class NoteCreate(BaseModel):
    tutor_id: str
    title: str
    subject: str
    description: str
    price: float = Field(ge=0)
    content: str


class NoteOut(BaseModel):
    id: str = Field(alias="_id")
    tutor_id: str
    title: str
    subject: str
    description: str
    price: float
    content: str | None = None
    rating: float = 0
    purchases_count: int = 0
    score: float | None = None
    reason: str | None = None

    model_config = {"populate_by_name": True}


class PurchaseRequest(BaseModel):
    student_id: str


class PurchaseOut(BaseModel):
    purchase_id: str
    note_id: str
    student_id: str
    status: str = "simulated_paid"
    message: str
