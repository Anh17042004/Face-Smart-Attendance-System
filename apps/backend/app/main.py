from fastapi import FastAPI

from app.api.v1.attendance import router as attendance_router
from app.api.v1.recognition import router as recognition_router

app = FastAPI(title="Face Smart Backend", version="0.1.0")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


app.include_router(attendance_router, prefix="/api/v1")
app.include_router(recognition_router, prefix="/api/v1")
