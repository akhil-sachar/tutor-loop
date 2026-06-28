from fastapi import APIRouter, Depends, HTTPException

from backend.app.api.deps import get_db, get_livekit
from backend.app.db.mongo import utc_now
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

    availability_slot = await db.find_one(
        "tutor_availability",
        {
            "tutor_id": payload.tutor_id,
            "starts_at": payload.starts_at,
            "duration_minutes": 30,
            "status": "available",
        },
    )
    if not availability_slot:
        next_slots = await db.find_many(
            "tutor_availability",
            {"tutor_id": payload.tutor_id, "status": "available"},
            sort=[("starts_at", 1)],
            limit=3,
        )
        raise HTTPException(
            status_code=409,
            detail={
                "message": "Tutor is not available for that 30-minute slot.",
                "next_available": [
                    {
                        "slot_id": slot["_id"],
                        "starts_at": slot["starts_at"],
                        "ends_at": slot["ends_at"],
                    }
                    for slot in next_slots
                ],
            },
        )

    booking = payload.model_dump()
    booking.update(
        {
            "status": "booked",
            "ends_at": availability_slot["ends_at"],
            "availability_slot_id": availability_slot["_id"],
            "topic": availability_slot.get("topic"),
        }
    )
    booking_id = await db.insert_one("bookings", booking)
    room_id = livekit.room_id_for_booking(booking_id)
    await db.update_one(
        "tutor_availability",
        {"_id": availability_slot["_id"], "status": "available"},
        {
            "$set": {
                "status": "booked",
                "booking_id": booking_id,
                "student_id": payload.student_id,
                "updated_at": utc_now(),
            }
        },
    )
    session = {
        "booking_id": booking_id,
        "availability_slot_id": availability_slot["_id"],
        "tutor_id": payload.tutor_id,
        "student_id": payload.student_id,
        "subject": payload.subject,
        "topic": availability_slot.get("topic"),
        "started_at": payload.starts_at,
        "ended_at": availability_slot["ends_at"],
        "duration_minutes": 30,
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
