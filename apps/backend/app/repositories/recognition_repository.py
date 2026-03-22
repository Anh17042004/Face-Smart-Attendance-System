from collections import defaultdict

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import MILVUS_TOP_K, MIRROR_EMBEDDING_TO_POSTGRES
from app.core.milvus_store import MilvusVectorStore
from app.models.face_embedding import FaceEmbedding
from app.models.user import User
from app.schemas.recognition import EnrollResponse, MatchBatchResponse


class RecognitionRepository:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.vector_store = MilvusVectorStore()

    def match_embeddings_batch(
        self,
        embeddings: list[list[float]],
        threshold: float,
        min_vote_count: int,
    ) -> MatchBatchResponse:
        score_by_code: dict[str, list[float]] = defaultdict(list)
        name_by_code: dict[str, str | None] = {}

        search_results = self.vector_store.search_embeddings(
            embeddings=embeddings,
            limit=MILVUS_TOP_K,
        )
        for per_frame_hits in search_results:
            if not per_frame_hits:
                continue

            best_hit = per_frame_hits[0]
            employee_code = best_hit.get("employee_code")
            user_name = best_hit.get("user_name")
            similarity = float(best_hit.get("similarity", 0.0))
            if not employee_code or similarity < threshold:
                continue

            score_by_code[employee_code].append(similarity)
            name_by_code[employee_code] = user_name

        if not score_by_code:
            return MatchBatchResponse(matched=False, vote_count=0, total_frames=len(embeddings))

        winner_code, winner_scores = max(score_by_code.items(), key=lambda kv: len(kv[1]))
        vote_count = len(winner_scores)
        if vote_count < min_vote_count:
            return MatchBatchResponse(
                matched=False,
                vote_count=vote_count,
                total_frames=len(embeddings),
            )

        avg_similarity = sum(winner_scores) / vote_count
        return MatchBatchResponse(
            matched=True,
            employee_code=winner_code,
            user_name=name_by_code.get(winner_code),
            similarity=float(avg_similarity),
            vote_count=vote_count,
            total_frames=len(embeddings),
        )

    def enroll_embedding(
        self,
        employee_code: str,
        user_name: str,
        embedding: list[float],
        model_version: str,
    ) -> EnrollResponse:
        try:
            user_stmt = select(User).where(User.employee_code == employee_code).limit(1)
            user = self.db.scalar(user_stmt)
            if user is None:
                user = User(employee_code=employee_code, name=user_name)
                self.db.add(user)
                self.db.flush()
            elif user.name != user_name:
                user.name = user_name

            vector_id = self.vector_store.insert_embedding(
                user_id=user.id,
                employee_code=employee_code,
                user_name=user_name,
                embedding=embedding,
                model_version=model_version,
            )

            mirrored_record_id: str | None = None
            if MIRROR_EMBEDDING_TO_POSTGRES:
                record = FaceEmbedding(
                    user_id=user.id,
                    embedding=embedding,
                    model_version=model_version,
                )
                self.db.add(record)
                self.db.flush()
                mirrored_record_id = record.id
                count_stmt = select(func.count(FaceEmbedding.id)).where(FaceEmbedding.user_id == user.id)
                total = int(self.db.scalar(count_stmt) or 0)
            else:
                total = self.vector_store.count_by_employee_code(employee_code=employee_code)

            self.db.commit()
        except Exception:
            self.db.rollback()
            raise

        return EnrollResponse(
            success=True,
            employee_code=employee_code,
            user_name=user_name,
            embedding_id=vector_id or mirrored_record_id,
            total_embeddings=total,
        )
