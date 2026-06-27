from enum import StrEnum


class UserRole(StrEnum):
    student = "student"
    tutor = "tutor"
    admin = "admin"


class BookingStatus(StrEnum):
    booked = "booked"
    live = "live"
    completed = "completed"
    reflected = "reflected"
    cancelled = "cancelled"


class RecommendationType(StrEnum):
    note = "note"
    tutor = "tutor"
    ai_lesson = "ai_lesson"
