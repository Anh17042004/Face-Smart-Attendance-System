from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.repositories.event_repository import PostgresEventRepository
from app.schemas.attendance import AttendanceEventIn, AttendanceEventOut
from app.services.attendance_service import AttendanceService

router = APIRouter(prefix="/attendance", tags=["attendance"])


def get_service(db: Session = Depends(get_db)) -> AttendanceService:
    repository = PostgresEventRepository(db)
    return AttendanceService(repository)


@router.post("/events", response_model=AttendanceEventOut)
def create_event(
    payload: AttendanceEventIn,
    service: AttendanceService = Depends(get_service),
) -> AttendanceEventOut:
    return service.create_event(payload)


@router.get("/events", response_model=list[AttendanceEventOut])
def list_events(
    limit: int = Query(default=50, ge=1, le=500),
    service: AttendanceService = Depends(get_service),
) -> list[AttendanceEventOut]:
    return service.list_recent_events(limit=limit)
