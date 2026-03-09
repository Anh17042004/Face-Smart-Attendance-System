from app.repositories.recognition_repository import RecognitionRepository
from app.schemas.recognition import EnrollResponse, MatchBatchResponse


class RecognitionService:
    def __init__(self, repository: RecognitionRepository) -> None:
        self.repository = repository

    def match_embeddings_batch(
        self,
        embeddings: list[list[float]],
        threshold: float,
        min_vote_count: int,
    ) -> MatchBatchResponse:
        return self.repository.match_embeddings_batch(
            embeddings=embeddings,
            threshold=threshold,
            min_vote_count=min_vote_count,
        )

    def enroll_embedding(
        self,
        employee_code: str,
        user_name: str,
        embedding: list[float],
        model_version: str,
    ) -> EnrollResponse:
        return self.repository.enroll_embedding(
            employee_code=employee_code,
            user_name=user_name,
            embedding=embedding,
            model_version=model_version,
        )
