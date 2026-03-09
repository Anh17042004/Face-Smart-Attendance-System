from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import (
    LATE_GRACE_MINUTES,
    SHIFT_END_HOUR,
    SHIFT_END_MINUTE,
    SHIFT_START_HOUR,
    SHIFT_START_MINUTE,
)
from app.models.attendance_log import AttendanceLog
from app.models.attendance_summary import AttendanceSummary
from app.models.device import Device
from app.models.user import User
from app.schemas.attendance import AttendanceEventIn, AttendanceEventOut


class PostgresEventRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def _resolve_event_type(self, requested_type: str, user_id: str | None) -> str:
        event_type = (requested_type or "").strip().lower()
        if event_type and event_type != "auto":
            return event_type

        if user_id is None:
            return "checkin"

        last_stmt = (
            select(AttendanceLog)
            .where(AttendanceLog.user_id == user_id)
            .order_by(AttendanceLog.timestamp.desc())
            .limit(1)
        )
        last_event = self.db.scalar(last_stmt)
        if last_event is None:
            return "checkin"
        return "checkout" if (last_event.type or "").lower() == "checkin" else "checkin"

    def _compute_attendance_status(self, resolved_type: str, event_time: datetime) -> str:
        local_dt = event_time.astimezone() if event_time.tzinfo else event_time
        if resolved_type == "checkin":
            shift_start = local_dt.replace(
                hour=SHIFT_START_HOUR,
                minute=SHIFT_START_MINUTE,
                second=0,
                microsecond=0,
            )
            late_deadline = shift_start + timedelta(minutes=LATE_GRACE_MINUTES)
            return "checkin_dung_gio" if local_dt <= late_deadline else "checkin_muon"

        shift_end = local_dt.replace(
            hour=SHIFT_END_HOUR,
            minute=SHIFT_END_MINUTE,
            second=0,
            microsecond=0,
        )
        return "checkout_ve_som" if local_dt < shift_end else "checkout_dung_gio"

    def _upsert_daily_summary(self, user_id: str, event_time: datetime, resolved_type: str, status: str) -> None:
        work_date = (event_time.astimezone() if event_time.tzinfo else event_time).date()
        stmt = (
            select(AttendanceSummary)
            .where(AttendanceSummary.user_id == user_id, AttendanceSummary.date == work_date)
            .limit(1)
        )
        summary = self.db.scalar(stmt)
        if summary is None:
            summary = AttendanceSummary(
                user_id=user_id,
                date=work_date,
                status=status,
            )
            self.db.add(summary)

        if resolved_type == "checkin":
            if summary.checkin_time is None or event_time < summary.checkin_time:
                summary.checkin_time = event_time
        elif resolved_type == "checkout":
            if summary.checkout_time is None or event_time > summary.checkout_time:
                summary.checkout_time = event_time

        if summary.status:
            parts = [p.strip() for p in summary.status.split(";") if p.strip()]
            parts = [p for p in parts if not p.startswith("checkin_") and not p.startswith("checkout_")]
        else:
            parts = []

        if resolved_type == "checkin":
            parts.append(status)
            if summary.checkout_time is not None:
                parts.append(
                    self._compute_attendance_status("checkout", summary.checkout_time)
                )
        else:
            if summary.checkin_time is not None:
                parts.append(
                    self._compute_attendance_status("checkin", summary.checkin_time)
                )
            parts.append(status)

        summary.status = ";".join(parts)
        self.db.add(summary)

    def append(self, payload: AttendanceEventIn) -> AttendanceEventOut:
        user_id: str | None = None
        if payload.employee_code:
            stmt = select(User).where(User.employee_code == payload.employee_code).limit(1)
            user = self.db.scalar(stmt)
            if user is not None:
                user_id = user.id

        resolved_device_id: str | None = None
        if payload.device_id:
            raw_device = payload.device_id.strip()
            if raw_device:
                # Accept either real device UUID or a human-readable device_code from client.
                device = self.db.scalar(select(Device).where(Device.id == raw_device).limit(1))
                if device is None:
                    device = self.db.scalar(select(Device).where(Device.device_code == raw_device).limit(1))
                if device is None:
                    device = Device(device_code=raw_device)
                    self.db.add(device)
                    self.db.flush()
                resolved_device_id = device.id

        image_url = None
        if isinstance(payload.metadata, dict):
            image_url = payload.metadata.get("image_url")

        resolved_type = self._resolve_event_type(payload.type, user_id)

        db_event = AttendanceLog(
            user_id=user_id,
            device_id=resolved_device_id,
            confidence=payload.similarity if payload.similarity is not None else payload.liveness_score,
            image_url=image_url,
            type=resolved_type,
        )
        self.db.add(db_event)
        self.db.flush()

        event_time = db_event.timestamp or datetime.now().astimezone()

        attendance_status = self._compute_attendance_status(resolved_type, event_time)
        if user_id:
            self._upsert_daily_summary(
                user_id=user_id,
                event_time=event_time,
                resolved_type=resolved_type,
                status=attendance_status,
            )

        self.db.commit()
        self.db.refresh(db_event)

        employee_code = payload.employee_code
        if employee_code is None and db_event.user_id:
            user_stmt = select(User).where(User.id == db_event.user_id).limit(1)
            db_user = self.db.scalar(user_stmt)
            employee_code = db_user.employee_code if db_user is not None else None

        return AttendanceEventOut(
            id=db_event.id,
            type=db_event.type,
            employee_code=employee_code,
            similarity=db_event.confidence,
            liveness_score=payload.liveness_score,
            device_id=payload.device_id,
            metadata={"image_url": db_event.image_url} if db_event.image_url else {},
            created_at=db_event.timestamp,
            attendance_status=attendance_status,
        )

    def list_recent(self, limit: int = 50) -> list[AttendanceEventOut]:
        stmt = (
            select(AttendanceLog, User.employee_code)
            .outerjoin(User, AttendanceLog.user_id == User.id)
            .order_by(AttendanceLog.timestamp.desc())
            .limit(limit)
        )
        rows = self.db.execute(stmt).all()
        return [
            AttendanceEventOut(
                id=log.id,
                type=log.type,
                employee_code=employee_code,
                similarity=log.confidence,
                liveness_score=None,
                device_id=log.device_id,
                metadata={"image_url": log.image_url} if log.image_url else {},
                created_at=log.timestamp,
                attendance_status=None,
            )
            for log, employee_code in rows
        ]
