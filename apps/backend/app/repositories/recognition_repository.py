import math
from collections import defaultdict

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.face_embedding import FaceEmbedding
from app.models.user import User
from app.schemas.recognition import EnrollResponse, MatchBatchResponse


def _normalize(vec: list[float]) -> list[float]:
    norm = math.sqrt(sum(v * v for v in vec))
    if norm <= 1e-12:
        return vec
    return [v / norm for v in vec]


def _cosine(a: list[float], b: list[float]) -> float:
    an = _normalize(a)
    bn = _normalize(b)
    return float(sum(x * y for x, y in zip(an, bn)))


class RecognitionRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def _load_embedding_rows(self):
        stmt = select(FaceEmbedding, User.employee_code, User.name).join(User, FaceEmbedding.user_id == User.id)
        return self.db.execute(stmt).all()

    def _match_single(self, embedding: list[float], threshold: float, rows):
        best_score = -1.0
        best_code = None
        best_name = None

        for face_emb, employee_code, user_name in rows:
            stored = list(face_emb.embedding)
            if len(stored) != len(embedding):
                continue
            score = _cosine(embedding, stored)
            if score > best_score:
                best_score = score
                best_code = employee_code
                best_name = user_name

        if best_score < threshold or best_code is None:
            return False, None, None, max(best_score, 0.0)

        return True, best_code, best_name, float(best_score)

    def match_embeddings_batch(
        self,
        embeddings: list[list[float]],
        threshold: float,
        min_vote_count: int,
    ) -> MatchBatchResponse:
        rows = self._load_embedding_rows()
        score_by_code: dict[str, list[float]] = defaultdict(list)
        name_by_code: dict[str, str | None] = {}

        for embedding in embeddings:
            matched, employee_code, user_name, similarity = self._match_single(
                embedding=embedding,
                threshold=threshold,
                rows=rows,
            )
            if matched and employee_code:
                score_by_code[employee_code].append(float(similarity))
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
        user_stmt = select(User).where(User.employee_code == employee_code).limit(1)
        user = self.db.scalar(user_stmt)
        if user is None:
            user = User(employee_code=employee_code, name=user_name)
            self.db.add(user)
            self.db.flush()
        elif user.name != user_name:
            user.name = user_name

        record = FaceEmbedding(
            user_id=user.id,
            embedding=embedding,
            model_version=model_version,
        )
        self.db.add(record)
        self.db.commit()
        self.db.refresh(record)

        count_stmt = select(func.count(FaceEmbedding.id)).where(FaceEmbedding.user_id == user.id)
        total = int(self.db.scalar(count_stmt) or 0)

        return EnrollResponse(
            success=True,
            employee_code=employee_code,
            user_name=user.name,
            embedding_id=record.id,
            total_embeddings=total,
        )
