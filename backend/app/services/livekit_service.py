from __future__ import annotations

import uuid
from typing import Any


class LiveKitService:
    def __init__(self, settings: Any):
        self.settings = settings

    def room_id_for_booking(self, booking_id: str) -> str:
        return f"tutorloop-{booking_id[:8]}"

    def create_token(self, *, room_id: str, identity: str, display_name: str | None = None) -> dict[str, Any]:
        if self.settings.use_livekit:
            try:
                # Sponsor integration: real LiveKit room token for the human
                # tutoring classroom.
                from livekit import api

                token = (
                    api.AccessToken(self.settings.livekit_api_key, self.settings.livekit_api_secret)
                    .with_identity(identity)
                    .with_name(display_name or identity)
                    .with_grants(api.VideoGrants(room_join=True, room=room_id))
                    .to_jwt()
                )
                return {
                    "room_id": room_id,
                    "room_url": self.settings.livekit_url,
                    "token": token,
                    "is_mock": False,
                }
            except Exception:
                pass

        return {
            "room_id": room_id,
            "room_url": f"/classroom.html?room_id={room_id}",
            "token": f"mock-livekit-token-{uuid.uuid4()}",
            "is_mock": True,
        }
