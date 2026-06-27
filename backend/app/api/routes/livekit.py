from fastapi import APIRouter, Depends, HTTPException

from backend.app.api.deps import get_db, get_livekit
from backend.app.schemas.bookings import LiveKitTokenOut, LiveKitTokenRequest

router = APIRouter(prefix="/livekit", tags=["livekit"])


@router.post("/token", response_model=LiveKitTokenOut)
async def create_livekit_token(payload: LiveKitTokenRequest, db=Depends(get_db), livekit=Depends(get_livekit)):
    booking = await db.find_one("bookings", {"_id": payload.booking_id})
    if not booking:
        raise HTTPException(status_code=404, detail="Booking not found")
    room_id = booking.get("room_id") or livekit.room_id_for_booking(payload.booking_id)
    return livekit.create_token(room_id=room_id, identity=payload.user_id, display_name=payload.display_name)
