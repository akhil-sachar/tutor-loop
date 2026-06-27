from __future__ import annotations

import json
import uuid
from typing import Any


class LiveKitService:
    AGENT_NAME = "tutorloop-ai-tutor"

    def __init__(self, settings: Any):
        self.settings = settings

    def room_id_for_booking(self, booking_id: str) -> str:
        return f"tutorloop-{booking_id[:8]}"

    def room_id_for_ai_lecture(self, lecture_id: str) -> str:
        return f"tutorloop-ai-{lecture_id[:12]}"

    def create_token(
        self,
        *,
        room_id: str,
        identity: str,
        display_name: str | None = None,
        agent_metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        if self.settings.use_livekit:
            try:
                from livekit import api

                grants = api.VideoGrants(
                    room_join=True,
                    room=room_id,
                    can_publish=True,
                    can_subscribe=True,
                )
                token_builder = (
                    api.AccessToken(self.settings.livekit_api_key, self.settings.livekit_api_secret)
                    .with_identity(identity)
                    .with_name(display_name or identity)
                    .with_grants(grants)
                )
                if agent_metadata:
                    token_builder = token_builder.with_room_config(
                        api.RoomConfiguration(
                            agents=[
                                api.RoomAgentDispatch(
                                    agent_name=self.AGENT_NAME,
                                    metadata=json.dumps(agent_metadata),
                                )
                            ]
                        )
                    )
                token = token_builder.to_jwt()
                return {
                    "room_id": room_id,
                    "room_url": self.settings.livekit_url,
                    "token": token,
                    "is_mock": False,
                    "agent_name": self.AGENT_NAME if agent_metadata else None,
                }
            except Exception:
                pass

        return {
            "room_id": room_id,
            "room_url": f"/ai-lecture.html?room_id={room_id}",
            "token": f"mock-livekit-token-{uuid.uuid4()}",
            "is_mock": True,
            "agent_name": self.AGENT_NAME if agent_metadata else None,
        }

    def create_ai_lecture_token(
        self,
        *,
        room_id: str,
        identity: str,
        display_name: str | None,
        agent_metadata: dict[str, Any],
    ) -> dict[str, Any]:
        return self.create_token(
            room_id=room_id,
            identity=identity,
            display_name=display_name,
            agent_metadata=agent_metadata,
        )
