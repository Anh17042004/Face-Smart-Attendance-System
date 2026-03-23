import os
from pathlib import Path

try:
    from dotenv import load_dotenv
except ModuleNotFoundError:  # pragma: no cover
    def load_dotenv(*_args, **_kwargs) -> bool:
        return False

load_dotenv(dotenv_path=Path(__file__).resolve().parents[2] / ".env", override=False)


DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+psycopg://postgres:postgres@localhost:5432/face_smart",
)

SHIFT_START_HOUR = int(os.getenv("SHIFT_START_HOUR", "8"))
SHIFT_START_MINUTE = int(os.getenv("SHIFT_START_MINUTE", "0"))
LATE_GRACE_MINUTES = int(os.getenv("LATE_GRACE_MINUTES", "15"))
SHIFT_END_HOUR = int(os.getenv("SHIFT_END_HOUR", "17"))
SHIFT_END_MINUTE = int(os.getenv("SHIFT_END_MINUTE", "30"))


def _env_bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


MILVUS_URI = os.getenv("MILVUS_URI", "http://localhost:19530")
MILVUS_TOKEN = os.getenv("MILVUS_TOKEN", "")
MILVUS_DB_NAME = os.getenv("MILVUS_DB_NAME", "default")
MILVUS_COLLECTION_NAME = os.getenv("MILVUS_COLLECTION_NAME", "face_embeddings")
MILVUS_VECTOR_DIM = int(os.getenv("MILVUS_VECTOR_DIM", "512"))
MILVUS_INDEX_TYPE = os.getenv("MILVUS_INDEX_TYPE", "HNSW")
MILVUS_METRIC_TYPE = os.getenv("MILVUS_METRIC_TYPE", "COSINE")
MILVUS_HNSW_M = int(os.getenv("MILVUS_HNSW_M", "16"))
MILVUS_HNSW_EF_CONSTRUCTION = int(os.getenv("MILVUS_HNSW_EF_CONSTRUCTION", "200"))
MILVUS_SEARCH_EF = int(os.getenv("MILVUS_SEARCH_EF", "64"))
MILVUS_TOP_K = int(os.getenv("MILVUS_TOP_K", "1"))

# Transitional mode: keep storing embeddings in PostgreSQL for audit/fallback.
MIRROR_EMBEDDING_TO_POSTGRES = _env_bool("MIRROR_EMBEDDING_TO_POSTGRES", True)
