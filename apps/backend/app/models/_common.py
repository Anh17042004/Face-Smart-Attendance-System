from __future__ import annotations

from datetime import datetime, timezone
import uuid


def new_uuid() -> str:
    return str(uuid.uuid4())


def utcnow() -> datetime:
    return datetime.now(timezone.utc)

