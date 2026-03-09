from pydantic import BaseModel, Field


class MatchBatchRequest(BaseModel):
    embeddings: list[list[float]] = Field(..., min_length=1)
    threshold: float = Field(default=0.4, ge=0.0, le=1.0)
    min_vote_count: int = Field(default=4, ge=1)


class MatchBatchResponse(BaseModel):
    matched: bool
    employee_code: str | None = None
    user_name: str | None = None
    similarity: float = 0.0
    vote_count: int = 0
    total_frames: int = 0


class EnrollRequest(BaseModel):
    employee_code: str
    user_name: str
    embedding: list[float] = Field(..., min_length=1)
    model_version: str = "arcface.onnx"


class EnrollResponse(BaseModel):
    success: bool
    employee_code: str
    user_name: str
    embedding_id: str | None = None
    total_embeddings: int
