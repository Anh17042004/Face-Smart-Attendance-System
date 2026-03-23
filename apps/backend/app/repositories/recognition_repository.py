from collections import defaultdict
from math import sqrt

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
        if not embeddings:
            return MatchBatchResponse(matched=False, vote_count=0, total_frames=0)

        vector_error: Exception | None = None
        score_by_code: dict[str, list[float]] = defaultdict(list)
        name_by_code: dict[str, str | None] = {}

        try:
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
        except Exception as exc:
            vector_error = exc

        if score_by_code:
            return self._build_vote_response(
                score_by_code=score_by_code,
                name_by_code=name_by_code,
                min_vote_count=min_vote_count,
                total_frames=len(embeddings),
            )

        if MIRROR_EMBEDDING_TO_POSTGRES:
            postgres_gallery = self._load_postgres_gallery()
            fallback_response = self._match_with_gallery(
                embeddings=embeddings,
                threshold=threshold,
                min_vote_count=min_vote_count,
                gallery=postgres_gallery,
            )
            # If Milvus had a hard error and there is no mirrored gallery data, bubble up.
            if vector_error is not None and not postgres_gallery:
                raise vector_error
            return fallback_response

        if vector_error is not None:
            raise vector_error

        return MatchBatchResponse(matched=False, vote_count=0, total_frames=len(embeddings))

    def _build_vote_response(
        self,
        score_by_code: dict[str, list[float]],
        name_by_code: dict[str, str | None],
        min_vote_count: int,
        total_frames: int,
    ) -> MatchBatchResponse:
        if not score_by_code:
            return MatchBatchResponse(matched=False, vote_count=0, total_frames=total_frames)

        winner_code, winner_scores = max(score_by_code.items(), key=lambda kv: len(kv[1]))
        vote_count = len(winner_scores)
        if vote_count < min_vote_count:
            return MatchBatchResponse(
                matched=False,
                vote_count=vote_count,
                total_frames=total_frames,
            )

        avg_similarity = sum(winner_scores) / vote_count
        return MatchBatchResponse(
            matched=True,
            employee_code=winner_code,
            user_name=name_by_code.get(winner_code),
            similarity=float(avg_similarity),
            vote_count=vote_count,
            total_frames=total_frames,
        )

    @staticmethod
    def _cosine_similarity(vec_a: list[float], vec_b: list[float]) -> float:
        if not vec_a or not vec_b or len(vec_a) != len(vec_b):
            return 0.0

        dot = 0.0
        norm_a = 0.0
        norm_b = 0.0
        for a, b in zip(vec_a, vec_b):
            af = float(a)
            bf = float(b)
            dot += af * bf
            norm_a += af * af
            norm_b += bf * bf

        if norm_a <= 1e-12 or norm_b <= 1e-12:
            return 0.0
        return float(dot / (sqrt(norm_a) * sqrt(norm_b)))

    def _load_postgres_gallery(self) -> list[tuple[str, str | None, list[float]]]:
        rows = self.db.execute(
            select(FaceEmbedding.embedding, User.employee_code, User.name).join(
                User,
                FaceEmbedding.user_id == User.id,
            )
        ).all()

        gallery: list[tuple[str, str | None, list[float]]] = []
        for embedding, employee_code, user_name in rows:
            if not employee_code or not isinstance(embedding, list):
                continue
            gallery.append((employee_code, user_name, embedding))
        return gallery

    def _match_with_gallery(
        self,
        embeddings: list[list[float]],
        threshold: float,
        min_vote_count: int,
        gallery: list[tuple[str, str | None, list[float]]],
    ) -> MatchBatchResponse:
        if not gallery:
            return MatchBatchResponse(matched=False, vote_count=0, total_frames=len(embeddings))

        score_by_code: dict[str, list[float]] = defaultdict(list)
        name_by_code: dict[str, str | None] = {}

        for query_embedding in embeddings:
            best_code: str | None = None
            best_name: str | None = None
            best_similarity = -1.0

            for employee_code, user_name, stored_embedding in gallery:
                similarity = self._cosine_similarity(query_embedding, stored_embedding)
                if similarity > best_similarity:
                    best_similarity = similarity
                    best_code = employee_code
                    best_name = user_name

            if best_code is not None and best_similarity >= threshold:
                score_by_code[best_code].append(best_similarity)
                name_by_code[best_code] = best_name

        return self._build_vote_response(
            score_by_code=score_by_code,
            name_by_code=name_by_code,
            min_vote_count=min_vote_count,
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
