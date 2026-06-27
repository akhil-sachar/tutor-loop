from fastapi import APIRouter, Depends, HTTPException

from backend.app.api.deps import get_reflections
from backend.app.schemas.sessions import ReflectRequest, ReflectionOut

router = APIRouter(prefix="/sessions", tags=["sessions"])


@router.post("/{session_id}/reflect", response_model=ReflectionOut)
async def reflect_session(session_id: str, payload: ReflectRequest, reflections=Depends(get_reflections)):
    try:
        return await reflections.reflect_session(
            session_id=session_id,
            transcript=payload.transcript,
            target_language=payload.target_language,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
