from pydantic import BaseModel


class LibraryNote(BaseModel):
    id: str
    title: str
    subject: str | None = None
    description: str = ""
    content: str = ""
    price: float = 0.0


class LibraryBook(BaseModel):
    id: str
    title: str
    subject: str | None = None
    description: str = ""
    author: str | None = None
    preview: str = ""


class StudentLibraryOut(BaseModel):
    student_id: str
    notes: list[LibraryNote]
    books: list[LibraryBook]
