from __future__ import annotations

from datetime import time

from sqlalchemy import Integer, String, Time
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models._common import new_uuid


class WorkShift(Base):
    __tablename__ = "work_shifts"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    start_time: Mapped[time] = mapped_column(Time(), nullable=False)
    end_time: Mapped[time] = mapped_column(Time(), nullable=False)
    late_threshold: Mapped[int] = mapped_column(Integer, nullable=False)
