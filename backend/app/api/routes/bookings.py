from fastapi import APIRouter, Depends, HTTPException

from backend.app.api.deps import get_db, get_livekit
from backend.app.schemas.bookings import BookingCreate, BookingOut

router = APIRouter(prefix="/bookings", tags=["bookings"])


@router.post("", response_model=BookingOut)
async def create_booking(payload: BookingCreate, db=Depends(get_db), livekit=Depends(get_livekit)):
    tutor = await db.find_one("tutors", {"_id": payload.tutor_id})
    student = await db.find_one("users", {"_id": payload.student_id})
    if not tutor:
        raise HTTPException(status_code=404, detail="Tutor not found")
    if not student:
        raise HTTPException(status_code=404, detail="Student not found")

    booking = payload.model_dump()
    booking.update({"status": "booked"})
    booking_id = await db.insert_one("bookings", booking)
    room_id = livekit.room_id_for_booking(booking_id)
    session = {
        "booking_id": booking_id,
        "tutor_id": payload.tutor_id,
        "student_id": payload.student_id,
        "subject": payload.subject,
        "room_id": room_id,
        "status": "booked",
        "content_type": "lesson_summary",
    }
    session_id = await db.insert_one("sessions", session)
    await db.update_one("bookings", {"_id": booking_id}, {"$set": {"room_id": room_id, "session_id": session_id}})
    booking.update({"_id": booking_id, "room_id": room_id, "session_id": session_id})
    return booking


@router.get("/{booking_id}", response_model=BookingOut)
async def get_booking(booking_id: str, db=Depends(get_db)):
    booking = await db.find_one("bookings", {"_id": booking_id})
    if not booking:
        raise HTTPException(status_code=404, detail="Booking not found")
    return booking
