from datetime import datetime
from typing import Any

from pydantic import AliasChoices, BaseModel, Field


class AttendanceEventIn(BaseModel):
    type: str = Field(
        ...,
        description="checkin/checkout",
        validation_alias=AliasChoices("type", "event_type"),
    )
    employee_code: str | None = Field(default=None)
    similarity: float | None = Field(default=None)
    liveness_score: float | None = Field(default=None)
    device_id: str | None = Field(default=None)
    metadata: dict[str, Any] = Field(default_factory=dict)


class AttendanceEventOut(AttendanceEventIn):
    id: str
    created_at: datetime
    attendance_status: str | None = None
