# Backend Architecture

Backend su dung `FastAPI + SQLAlchemy + Alembic + PostgreSQL + Milvus`.

## Muc Tieu

- Nhan su kien cham cong tu desktop client.
- Cung cap API match/enroll embedding qua Milvus cho desktop client (online-only).
- Luu/tra cuu du lieu cham cong tren PostgreSQL.
- Quan ly schema DB theo version bang Alembic.

## Cau Truc Thu Muc

- `app/main.py`: entrypoint FastAPI.
- `app/api/v1/`: router API.
- `app/core/`: config DB, SQLAlchemy session.
- `app/models/`: ORM model (cac bang PostgreSQL).
- `app/repositories/`: truy cap du lieu.
- `app/services/`: nghiep vu.
- `migrations/`: Alembic migration scripts.
- `alembic.ini`: cau hinh Alembic.

## Luong Du Lieu

`Desktop Client -> /api/v1/recognition/* -> Service -> Repository -> Milvus`

`Desktop Client -> /api/v1/attendance/events -> Service -> Repository -> PostgreSQL`

## Databases

- PostgreSQL URL doc tu env var `DATABASE_URL`.
- Gia tri mac dinh:

```bash
postgresql+psycopg://postgres:postgres@localhost:5432/face_smart
```

- Milvus URL doc tu env var `MILVUS_URI`.
- Gia tri mac dinh:

```bash
http://localhost:19530
```

### Cac Bang Chinh

- `users`
- `face_embeddings`
- `devices`
- `attendance_logs`
- `work_shifts`
- `attendance_summary`
- `departments`

## Cai Dat

```bash
pip install -r requirements.txt
```

## Chay PostgreSQL + Milvus Bang Docker

Tai `apps/backend` da co san:

- `docker-compose.yml`
- `.env.example`

Tao file `.env` tu mau:

```bash
copy .env.example .env
```

Bat tat ca service:

```bash
docker compose up -d
```

Kiem tra trang thai:

```bash
docker compose ps
```

Tat tat ca service:

```bash
docker compose down
```

Neu chi muon bat rieng tung service:

```bash
docker compose up -d postgres
docker compose up -d etcd minio milvus
```

## Chay Migration

Apply schema hien tai:

```bash
alembic upgrade head
```

Tao migration moi sau khi doi model:

```bash
alembic revision --autogenerate -m "update schema"
alembic upgrade head
```

## Chay API

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

## Milvus Config Chinh

Trong `app/core/config.py`:

- `MILVUS_URI`
- `MILVUS_DB_NAME`
- `MILVUS_COLLECTION_NAME`
- `MILVUS_VECTOR_DIM`
- `MILVUS_INDEX_TYPE` (mac dinh `HNSW`)
- `MILVUS_METRIC_TYPE` (mac dinh `COSINE`)
- `MILVUS_TOP_K`
- `MIRROR_EMBEDDING_TO_POSTGRES`

## Endpoints Hien Tai

- `GET /health`
- `POST /api/v1/attendance/events`
- `GET /api/v1/attendance/events?limit=50`
- `POST /api/v1/recognition/match-batch`
- `POST /api/v1/recognition/enroll`

## Admin UI (Noi Bo)

Admin dashboard duoc tach rieng, khong mount vao API chinh.

```bash
python run_admin_ui.py
```

Mo tren: `http://127.0.0.1:8010`

## Kiem Tra Nhanh PostgreSQL Local

Neu chua chac DB da chay local hay chua, dung PowerShell:

```bash
Get-Command psql -ErrorAction SilentlyContinue
Get-Service | Where-Object { $_.Name -match 'postgres' -or $_.DisplayName -match 'PostgreSQL' }
Get-NetTCPConnection -State Listen | Where-Object { $_.LocalPort -eq 5432 }
```
