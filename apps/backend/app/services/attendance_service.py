from app.repositories.event_repository import PostgresEventRepository
from app.schemas.attendance import AttendanceEventIn, AttendanceEventOut


class AttendanceService:
    def __init__(self, repository: PostgresEventRepository) -> None:
        self.repository = repository

    def create_event(self, payload: AttendanceEventIn) -> AttendanceEventOut:
        return self.repository.append(payload)

    def list_recent_events(self, limit: int = 50) -> list[AttendanceEventOut]:
        return self.repository.list_recent(limit=limit)
