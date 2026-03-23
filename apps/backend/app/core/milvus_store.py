from __future__ import annotations

from datetime import datetime, timezone
import threading

from pymilvus import Collection, CollectionSchema, DataType, FieldSchema, connections, utility

from app.core.config import (
    MILVUS_COLLECTION_NAME,
    MILVUS_DB_NAME,
    MILVUS_HNSW_EF_CONSTRUCTION,
    MILVUS_HNSW_M,
    MILVUS_INDEX_TYPE,
    MILVUS_METRIC_TYPE,
    MILVUS_SEARCH_EF,
    MILVUS_TOKEN,
    MILVUS_URI,
    MILVUS_VECTOR_DIM,
)


class MilvusVectorStore:
    _collection: Collection | None = None
    _init_lock = threading.Lock()

    def __init__(self) -> None:
        self.collection = self._ensure_collection()

    @classmethod
    def _ensure_connected(cls) -> None:
        # Idempotent connect call; pymilvus reuses the alias if already connected.
        connect_args: dict[str, str] = {
            "alias": "default",
            "uri": MILVUS_URI,
        }
        if MILVUS_TOKEN.strip():
            connect_args["token"] = MILVUS_TOKEN.strip()
        if MILVUS_DB_NAME.strip():
            connect_args["db_name"] = MILVUS_DB_NAME.strip()
        connections.connect(**connect_args)

    @classmethod
    def _index_params(cls) -> dict:
        index_type = MILVUS_INDEX_TYPE.strip().upper()
        metric_type = MILVUS_METRIC_TYPE.strip().upper()

        if index_type == "HNSW":
            return {
                "index_type": "HNSW",
                "metric_type": metric_type,
                "params": {
                    "M": MILVUS_HNSW_M,
                    "efConstruction": MILVUS_HNSW_EF_CONSTRUCTION,
                },
            }

        if index_type == "IVF_FLAT":
            return {
                "index_type": "IVF_FLAT",
                "metric_type": metric_type,
                "params": {"nlist": 1024},
            }

        return {
            "index_type": "HNSW",
            "metric_type": metric_type,
            "params": {
                "M": MILVUS_HNSW_M,
                "efConstruction": MILVUS_HNSW_EF_CONSTRUCTION,
            },
        }

    @classmethod
    def _search_params(cls) -> dict:
        metric_type = MILVUS_METRIC_TYPE.strip().upper()
        index_type = MILVUS_INDEX_TYPE.strip().upper()
        if index_type == "IVF_FLAT":
            return {"metric_type": metric_type, "params": {"nprobe": 16}}
        return {"metric_type": metric_type, "params": {"ef": MILVUS_SEARCH_EF}}

    @classmethod
    def _ensure_collection(cls) -> Collection:
        if cls._collection is not None:
            return cls._collection

        with cls._init_lock:
            if cls._collection is not None:
                return cls._collection

            cls._ensure_connected()
            if not utility.has_collection(MILVUS_COLLECTION_NAME):
                fields = [
                    FieldSchema(name="id", dtype=DataType.INT64, is_primary=True, auto_id=True),
                    FieldSchema(name="user_id", dtype=DataType.VARCHAR, max_length=36),
                    FieldSchema(name="employee_code", dtype=DataType.VARCHAR, max_length=100),
                    FieldSchema(name="user_name", dtype=DataType.VARCHAR, max_length=255),
                    FieldSchema(name="model_version", dtype=DataType.VARCHAR, max_length=100),
                    FieldSchema(name="created_at", dtype=DataType.INT64),
                    FieldSchema(name="embedding", dtype=DataType.FLOAT_VECTOR, dim=MILVUS_VECTOR_DIM),
                ]
                schema = CollectionSchema(fields=fields, description="Face embeddings for attendance")
                collection = Collection(name=MILVUS_COLLECTION_NAME, schema=schema)
                collection.create_index(field_name="embedding", index_params=cls._index_params())
            else:
                collection = Collection(name=MILVUS_COLLECTION_NAME)

            if not collection.indexes:
                collection.create_index(field_name="embedding", index_params=cls._index_params())

            collection.load()
            cls._collection = collection
            return collection

    @staticmethod
    def _similarity(raw_score: float) -> float:
        metric_type = MILVUS_METRIC_TYPE.strip().upper()
        if metric_type in {"COSINE", "IP"}:
            return float(raw_score)
        if metric_type == "L2":
            return 1.0 / (1.0 + float(raw_score))
        return float(raw_score)

    def search_embeddings(self, embeddings: list[list[float]], limit: int = 1) -> list[list[dict]]:
        if not embeddings:
            return []

        result = self.collection.search(
            data=embeddings,
            anns_field="embedding",
            param=self._search_params(),
            limit=max(1, int(limit)),
            output_fields=["employee_code", "user_name"],
        )

        formatted: list[list[dict]] = []
        for hits in result:
            per_query: list[dict] = []
            for hit in hits:
                entity = hit.entity
                employee_code = entity.get("employee_code") if entity is not None else None
                user_name = entity.get("user_name") if entity is not None else None
                raw_score = float(getattr(hit, "score", getattr(hit, "distance", 0.0)))
                per_query.append(
                    {
                        "employee_code": employee_code,
                        "user_name": user_name,
                        "similarity": self._similarity(raw_score),
                    }
                )
            formatted.append(per_query)
        return formatted

    def insert_embedding(
        self,
        user_id: str,
        employee_code: str,
        user_name: str,
        embedding: list[float],
        model_version: str,
    ) -> str | None:
        # Row-based payload format for pymilvus 2.6.x.
        payload = [
            {
                "user_id": user_id,
                "employee_code": employee_code,
                "user_name": user_name,
                "model_version": model_version,
                "created_at": int(datetime.now(timezone.utc).timestamp()),
                "embedding": embedding,
            }
        ]
        insert_result = self.collection.insert(payload)
        self.collection.flush()
        if not insert_result.primary_keys:
            return None
        return str(insert_result.primary_keys[0])

    def count_by_employee_code(self, employee_code: str, limit: int = 10000) -> int:
        safe_code = employee_code.replace("\\", "\\\\").replace('"', '\\"')
        rows = self.collection.query(
            expr=f'employee_code == "{safe_code}"',
            output_fields=["id"],
            limit=max(1, int(limit)),
        )
        return len(rows)
