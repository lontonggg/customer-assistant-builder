# Backend Run Guide

## Prerequisites

- Python 3.10+ (recommended 3.11)
- Access to Mistral API
- Access to ElevenLabs API (for voice features)
- Postgres/Supabase credentials (for knowledge ingestion)

## Setup

1. Go to backend folder:
   - `cd backend`
2. Create env file:
   - Copy `backend/.env.example` to `backend/.env`
3. Configure data entry env file:
   - Copy `backend/data_entry/.env.example` to `backend/data_entry/.env`
4. (Optional) Create and activate virtual env:
   - `python -m venv .venv`
   - `source .venv/bin/activate` (macOS/Linux)
5. Install dependencies:
   - `pip install -r requirements.txt`

## Run

- Start server:
  - `python main.py`
- Server URL:
  - `http://localhost:8000`

## Quick Check

- Health endpoint:
  - `GET http://localhost:8000/`
- Expected response:
  - `{"status":"ok","service":"chat-backend"}`

## Notes

- SQLite (`backend/app.db`) is used for app/session data.
- Knowledge base ingestion is sent to Postgres/Supabase via `backend/data_entry/db_ingest.py`.
- OCR runs from `backend/data_entry/main.py`.

## Backend Structure

```
backend/
├─ main.py                 # FastAPI routes and endpoint orchestration
├─ app/
│  ├─ config.py            # Runtime config, paths, environment loading
│  ├─ schemas.py           # Pydantic request/response schemas
│  ├─ database.py          # SQLite init, connection helpers, row mappers
│  └─ services.py          # Chat generation, knowledge ingest, OCR utility helpers
├─ data_entry/
│  ├─ main.py              # OCR + structured extraction pipeline
│  └─ db_ingest.py         # Postgres/Supabase ingestion layer
├─ customer_agent/         # Agent package files
└─ uploads/                # Runtime uploaded/temporary files
```

### Structure Notes

- `main.py` should stay thin and endpoint-centric; keep parsing/validation and HTTP mapping here, but move reusable logic into `app/`.
- `app/config.py` centralizes environment/path configuration so constants are not duplicated across routes/services.
- `app/services.py` contains cross-endpoint workflows (chat response generation, OCR processing handoff, Supabase ingestion orchestration).
- `data_entry/` is treated as the extraction/ingestion subsystem, separated from API routing to keep concerns clean and testable.
