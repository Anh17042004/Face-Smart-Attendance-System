import os


DATABASE_URL = os.getenv(
	"DATABASE_URL",
	"postgresql+psycopg://postgres:postgres@localhost:5432/face_smart",
)

SHIFT_START_HOUR = int(os.getenv("SHIFT_START_HOUR", "8"))
SHIFT_START_MINUTE = int(os.getenv("SHIFT_START_MINUTE", "0"))
LATE_GRACE_MINUTES = int(os.getenv("LATE_GRACE_MINUTES", "15"))
SHIFT_END_HOUR = int(os.getenv("SHIFT_END_HOUR", "17"))
SHIFT_END_MINUTE = int(os.getenv("SHIFT_END_MINUTE", "30"))
