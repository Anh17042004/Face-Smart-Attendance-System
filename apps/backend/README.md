# Backend Architecture

Backend su dung `FastAPI + SQLAlchemy + Alembic + PostgreSQL`.

## Muc Tieu

- Nhan su kien cham cong tu desktop client.
- Cung cap API match/enroll embedding cho desktop client (online-only).
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

`Desktop Client -> /api/v1/recognition/* -> Service -> Repository -> PostgreSQL`

`Desktop Client -> /api/v1/attendance/events -> Service -> Repository -> PostgreSQL`

## Database

- DB URL doc tu env var `DATABASE_URL`.
- Gia tri mac dinh trong code:

```bash
postgresql+psycopg://postgres:postgres@localhost:5432/face_smart
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

## Chay PostgreSQL Bang Docker

Tai `apps/backend` da co san:

- `docker-compose.yml`
- `.env`

Bat PostgreSQL:

```bash
docker compose up -d
```

Kiem tra trang thai:

```bash
docker compose ps
```

Tat PostgreSQL:

```bash
docker compose down
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
