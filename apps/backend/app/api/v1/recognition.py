from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.repositories.recognition_repository import RecognitionRepository
from app.schemas.recognition import (
    EnrollRequest,
    EnrollResponse,
    MatchBatchRequest,
    MatchBatchResponse,
)
from app.services.recognition_service import RecognitionService

router = APIRouter(prefix="/recognition", tags=["recognition"])


def get_service(db: Session = Depends(get_db)) -> RecognitionService:
    repository = RecognitionRepository(db)
    return RecognitionService(repository)


@router.post("/match-batch", response_model=MatchBatchResponse)
def match_embeddings_batch(
    payload: MatchBatchRequest,
    service: RecognitionService = Depends(get_service),
) -> MatchBatchResponse:
    return service.match_embeddings_batch(
        embeddings=payload.embeddings,
        threshold=payload.threshold,
        min_vote_count=payload.min_vote_count,
    )


@router.post("/enroll", response_model=EnrollResponse)
def enroll_embedding(
    payload: EnrollRequest,
    service: RecognitionService = Depends(get_service),
) -> EnrollResponse:
    try:
        return service.enroll_embedding(
            employee_code=payload.employee_code,
            user_name=payload.user_name,
            embedding=payload.embedding,
            model_version=payload.model_version,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
